from logging import getLogger

from django.conf import settings

from vms.models import Vm, VmTemplate, Image, Subnet, IPAddress, Dc
from gui.models import User
from api.vm.base.utils import vm_update_ipaddress_usage
from api.vm.define.serializers import VmDefineSerializer, VmDefineNicSerializer

logger = getLogger(__name__)


# noinspection PyUnusedLocal
def get_vms(request, where=None, sr=('node',), order_by=('hostname',), **kwargs):
    """Similar to api.vm.utils.get_vms(), but this can be used only by SuperAdmins, to display all VMs
    (including slave-replicated related to a compute node"""
    if sr:
        qs = Vm.objects.filter(**kwargs).select_related(*sr)
    else:
        qs = Vm.objects.filter(**kwargs)

    if where:
        return qs.filter(where).order_by(*order_by)
    else:
        return qs.order_by(*order_by)


def _vm_save_ip_from_json(vm, net, ipaddress, allowed_ips=False):
    try:
        ip = net.ipaddress_set.get(ip=ipaddress)
    except IPAddress.DoesNotExist:
        ip = IPAddress(subnet=net, ip=ipaddress, usage=IPAddress.VM_REAL)
        logger.warning('Adding new IP %s into subnet %s for server %s', ip.ip, net.name, vm)
    else:
        if ip.vm:
            err = 'IP %s in subnet %s for server %s is already taken!' % (ip.ip, net.name, vm)
            return ip, err

    if allowed_ips:
        ip.vms.add(vm)
    else:
        ip.vm = vm
        ip.save()

    logger.info('Server %s association with IP %s (%s) was successfully saved', vm, ip.ip, net.name)

    return ip, None


def vm_from_json(request, task_id, json, dc, owner=settings.ADMIN_USER, template=True, save=False,  # noqa: R701
                 update_ips=True, update_dns=True):
    """Parse json a create new Vm object

    @param dict json: loaded json dictionary obtained via vmadm get
    @param int owner: whether to fetch the vm.owner User object. Also indicates an user id, \
    which will be used as fallback
    @param bool template: True if the template should be set according to internal_metadata.template
    @param Dc dc: Dc object for the Vm
    @param bool save: Should the new Vm be saved in DB?
    @param bool update_ips: Update server <-> IpAddress relations. Only performed if save and update_ips are True.
    @param bool update_dns: Try to update/create DNS record for server's primary IP. Only performed if save is True.
    @return: new Vm instance
    """
    # noinspection PyUnresolvedReferences
    hostname_length = VmDefineSerializer.base_fields['hostname'].max_length
    # noinspection PyUnresolvedReferences
    alias_length = VmDefineSerializer.base_fields['alias'].max_length
    # basic information (KeyError)
    vm = Vm(uuid=json['uuid'], hostname=json['hostname'][:hostname_length], status=Vm.STATUS_DICT[json['state']], dc=dc)
    vm.new = True
    brand = json['brand']

    # json and json_active
    vm.json = vm.json_active = json

    # node & vnc_port (no check)
    vm.node_id = json.get('server_uuid', None)
    vm.vnc_port = json.get('vnc_port', None)

    # alias
    try:
        vm.alias = json['internal_metadata']['alias'][:alias_length]
    except KeyError:
        try:
            alias = json['alias']
        except KeyError:
            alias = vm.hostname

        vm.alias = alias.split('.')[0][:alias_length]
        logger.warning('Alias for new VM %s could not be auto-detected. Fallback to alias=%s', vm, vm.alias)

    # ostype
    try:
        vm.ostype = int(json['internal_metadata']['ostype'])
    except KeyError:
        if brand == 'lx':
            vm.ostype = Vm.LINUX_ZONE
        elif brand == 'joyent':
            vm.ostype = Vm.SUNOS_ZONE
        else:  # brand == 'kvm' or brand == 'bhyve':
            vm.ostype = Vm.LINUX
        logger.warning('OS type for new VM %s could not be auto-detected. Fallback to ostype=%s', vm, vm.ostype)

    vm.hvm_type = vm.brand_to_hvm_type(vm.brand)

    # owner
    if owner:
        try:
            vm.owner = User.objects.get(id=int(json['owner_uuid']))
        except (KeyError, ValueError, User.DoesNotExist):
            vm.owner = User.objects.get(id=owner)
            logger.warning('Owner for new VM %s could not be auto-detected. Fallback to owner=%s', vm, vm.owner)

    # template
    if template:
        tmpname = None
        try:
            tmpname = json['internal_metadata']['template']
            if tmpname:
                vm.template = VmTemplate.objects.get(name=json['internal_metadata']['template'], dc=dc)
        except (KeyError, VmTemplate.DoesNotExist):
            vm.template = None
            if tmpname:
                logger.warning('Template "%s" for new VM %s could not be auto-detected', tmpname, vm)

    # images
    for img_uuid in vm.get_image_uuids():
        Image.objects.get(uuid=img_uuid, dc=dc)  # May raise Image.DoesNotExist

    # subnets
    for net_uuid in vm.get_network_uuids():
        if not Subnet.objects.filter(uuid=net_uuid, dc=dc).exists():
            # VM uses subnet that doesn't exist in database. Let's create it.

            # retrieve nic config for the non-existent network from harvested VM
            nic = vm.get_nic_config(net_uuid)
            network = IPAddress.get_net_address(nic['ip'], nic['netmask'])

            logger.warning('VM "%s" uses undefined network "%s/%s" over nic tag "%s". Trying to create it.',
                           vm.name, network, nic['netmask'], nic['nic_tag'])

            # take the network name from the nic tag
            net_name = nic['nic_tag']
            if Subnet.objects.filter(name=net_name).exists():
                logger.info('Network "%s" already exists, adding number at the end', net_name)
                net_name_number = 1
                while net_name_number < 100:
                    net_name = "%s-%s" % (net_name, net_name_number)
                    if not Subnet.objects.filter(name=net_name).exists():
                        # this name doesn't exist, let's use it
                        break
                    # if there really exist 99 networks with name "${net_name}-${net_name_number},
                    # subnet creation will fail
                    net_name_number += 1

            gateway = None
            if 'gateway' in nic:
                gateway = nic['gateway']

            mtu = None
            if 'mtu' in nic:
                mtu = nic['mtu']

            # create the network
            new_network = Subnet(name=net_name, uuid=net_uuid, nic_tag=nic['nic_tag'], mtu=mtu, network=network,
                       netmask=nic['netmask'], gateway=gateway, owner_id=settings.ADMIN_USER, alias=net_name)
            new_network.save()

            # attach network to specified dc
            new_network.dc.add(dc)
            if dc.name == settings.VMS_DC_ADMIN:
                # when attaching network to admin DC, attach it also to main dc
                main_dc = Dc.objects.get(name=settings.VMS_DC_MAIN)
                new_network.dc.add(main_dc)

    # Initialize uptime now
    logger.info(vm.update_uptime(force_init=True))

    if save:
        vm.save(sync_json=True, update_node_resources=True, update_storage_resources=True)
        logger.info('Server %s (%s) was saved', vm.uuid, vm)
        exc = None
        primary_ip = None

        if update_ips:
            for i, nic in enumerate(vm.json_get_nics()):
                if 'network_uuid' not in nic:
                    logger.error('Server %s NIC ID %s has no network_uuid defined', vm, i)
                    exc = KeyError('network_uuid')
                    break

                try:
                    net = Subnet.objects.get(uuid=nic['network_uuid'], dc=dc)
                except Subnet.DoesNotExist as e:
                    exc = e
                    break
                else:
                    if net.dhcp_passthrough:
                        logger.info('Server %s NIC ID %s uses an externally managed network %s', vm, i, net.name)
                        continue

                ip, err = _vm_save_ip_from_json(vm, net, nic['ip'], allowed_ips=False)

                if err:
                    logger.critical(err)
                    exc = SystemError(err)
                    break

                if i == 0:
                    primary_ip = ip

                for ipaddress in nic.get('allowed_ips', []):
                    _, err = _vm_save_ip_from_json(vm, net, ipaddress, allowed_ips=True)

                    if err:
                        logger.critical(err)
                        exc = SystemError(err)
                        break

        if exc:
            vm.delete()
            logger.info('Server %s was deleted', json['uuid'])
            raise exc

        try:
            vm_update_ipaddress_usage(vm)
        except ValueError as exc:
            vm.delete()
            logger.info('Server %s was deleted', json['uuid'])
            raise exc

        if update_dns and primary_ip:
            # This will fail silently (exception is logged)
            VmDefineNicSerializer.save_a(request, task_id, vm, primary_ip)

            if primary_ip.subnet.ptr_domain:
                # This will fail silently (exception is logged)
                VmDefineNicSerializer.save_ptr(request, task_id, vm, primary_ip, primary_ip.subnet, content=vm.hostname)

    return vm
