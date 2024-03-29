from api.task.tasks import task_log_cb_success
from api.task.utils import callback
from api.vm.base.utils import vm_update
from que.exceptions import TaskException
from que.mgmt import MgmtCallbackTask
from que.tasks import cq, get_task_logger
from vms.models import Vm, SlaveVm
from vms.signals import vm_node_changed

__all__ = ('vm_migrate_cb',)

logger = get_task_logger(__name__)


# noinspection PyUnusedLocal
def _vm_migrate_cb_failed(result, task_id, vm, ghost_vm):
    """
    Callback helper for failed task - revert VM status and remove dummy VM.
    """
    vm.revert_notready()
    ghost_vm.delete()


@cq.task(name='api.vm.migrate.tasks.vm_migrate_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_migrate_cb(result, task_id, vm_uuid=None, slave_vm_uuid=None):
    """
    A callback function for api.vm.migrate.views.vm_migrate.
    """
    ghost_vm = SlaveVm.get_by_uuid(slave_vm_uuid)
    msg = result.get('message', '')

    if result['returncode'] == 0 and msg and 'Successfully migrated' in msg:
        # Save node and delete placeholder VM first
        node = ghost_vm.vm.node
        nss = set(ghost_vm.vm.get_node_storages())  # New node storages
        ghost_vm.delete()  # post_delete signal will update node and storage resources
        # Fetch VM after ghost_vm is deleted, because it updates vm.slave_vms array
        vm = Vm.objects.select_related('node', 'dc').get(uuid=vm_uuid)
        nss.update(list(vm.get_node_storages()))  # Old node storages
        changing_node = vm.node != ghost_vm.vm.node
        json = result.pop('json', None)

        try:  # save json from smartos
            json_active = vm.json.load(json)
            vm.json_active = json_active
            vm.json = json_active
        except Exception as e:
            logger.exception(e)
            logger.error('Could not parse json output from vm_migrate(%s). Error: %s', vm_uuid, e)
            raise TaskException(result, 'Could not parse json output')

        # Revert status and set new node (should trigger node resource update)
        vm.revert_notready(save=False)
        keep_vnc_port = False

        if changing_node:
            vm.set_node(node)

            if vm.is_hvm():
                # The VNC port was changed during migration
                vm.vnc_port = json_active['vnc_port']
                assert ghost_vm.vm.vnc_port == vm.vnc_port
                keep_vnc_port = True

        vm.save(update_node_resources=True, update_storage_resources=nss, keep_vnc_port=keep_vnc_port)
        SlaveVm.switch_vm_snapshots_node_storages(vm, nss=nss)
        vm_node_changed.send(task_id, vm=vm, force_update=True)  # Signal!

    else:
        vm = Vm.objects.get(uuid=vm_uuid)
        _vm_migrate_cb_failed(result, task_id, vm, ghost_vm)
        logger.error('Found nonzero returncode in result from vm_migrate(%s). Error: %s', vm_uuid, msg)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg))

    task_log_cb_success(result, task_id, vm=vm, **result['meta'])

    if vm.json_changed():
        vm_update(vm)

    return result
