from django.urls import path, re_path, include
from django.conf import settings

from api.vm.views import vm_screenshot, vm_qga, vm_dc, vm_migrate, vm_backup, vm_define, vm_manage, vm_snapshot, \
    vm_backup_list, vm_define_disk, vm_define_list, vm_define_nic, vm_status_list, vm_define_backup, \
    vm_define_disk_list, vm_define_nic_list, vm_define_revert, vm_define_snapshot, vm_snapshot_list, \
    vm_define_backup_list, vm_define_snapshot_list, vm_define_snapshot_list_all, vm_list, vm_status, image_snapshot

urlpatterns = [
    # other
    # /vm/<hostname_or_uuid>/screenshot - get, create
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/screenshot/$', vm_screenshot, name='api_vm_screenshot'),

    # qga
    # /vm/<hostname_or_uuid>/qga/<command> - set
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/qga/(?P<command>[A-Za-z0-9_-]+)/$', vm_qga, name='api_vm_qga'),

    # migrate
    # /vm/<hostname_or_uuid>/migrate/dc - set
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/migrate/dc/$', vm_dc, name='api_vm_dc'),
    # /vm/<hostname_or_uuid>/migrate - set
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/migrate/$', vm_migrate, name='api_vm_migrate'),

    # define snapshot report
    path('define/snapshot/', vm_define_snapshot_list_all, name='api_vm_define_snapshot_list_all'),

    # snapshot
    # /vm/<hostname_or_uuid>/snapshot - get, set, delete
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/snapshot/$', vm_snapshot_list, name='api_vm_snapshot_list'),
    # /vm/<hostname_or_uuid>/snapshot/<snapname> - get, create, set, delete
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/snapshot/(?P<snapname>[A-Za-z0-9\._-]+)/$', vm_snapshot,
            name='api_vm_snapshot'),

    # status
    # /vm/status - get
    path('status/', vm_status_list, name='api_vm_status_list'),
    # /vm/<hostname_or_uuid>/status - get
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/status/$', vm_status, name='api_vm_status'),
    # /vm/<hostname_or_uuid>/status/{current|start|stop|restart} - get, set
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/status/(?P<action>(current|start|stop|reboot))/$', vm_status,
            name='api_vm_status'),

    # define
    # /vm/define - get
    path('define/', vm_define_list, name='api_vm_define_list'),
    # /vm/<hostname_or_uuid>/define - get, create, set, delete
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/define/$', vm_define, name='api_vm_define'),
    # /vm/<hostname_or_uuid>/define/revert - set
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/define/(undo|revert)/$', vm_define_revert,
            name='api_vm_define_revert'),
    # /vm/<hostname_or_uuid>/define/disk - get
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/define/disk/$', vm_define_disk_list,
            name='api_vm_define_disk_list'),
    # /vm/<hostname_or_uuid>/define/disk/<disk_id> - get, create, set, delete
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/define/disk/(?P<disk_id>\d)/$', vm_define_disk,
            name='api_vm_define_disk'),
    # /vm/<hostname_or_uuid>/define/nic - get
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/define/nic/$', vm_define_nic_list, name='api_vm_define_nic_list'),
    # /vm/<hostname_or_uuid>/define/nic/<nic_id> - get, create, set, delete
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/define/nic/(?P<nic_id>\d{1,2})/$', vm_define_nic,
            name='api_vm_define_nic'),

    # define snapshot
    # /vm/<hostname_or_uuid>/define/snapshot - get
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/define/snapshot/$', vm_define_snapshot_list,
            name='api_vm_define_snapshot_list'),
    # /vm/<hostname_or_uuid>/define/snapshot/<snapdef> - get, create, set, delete
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/define/snapshot/(?P<snapdef>[A-Za-z0-9\._-]+)/$',
            vm_define_snapshot, name='api_vm_define_snapshot'),

    # image from snapshot
    # /vm/<hostname_or_uuid>/snapshot/<snapname>/image/<name> - create
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)'
            r'/snapshot/(?P<snapname>[A-Za-z0-9\._-]+)/image/(?P<name>[A-Za-z0-9\._-]+)/$', image_snapshot,
            name='api_image_snapshot'),

    # base
    # /vm - get
    path(r'', vm_list, name='api_vm_list'),
    # /vm/<hostname_or_uuid> - get, create, set, delete
    re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/$', vm_manage, name='api_vm_manage'),
]

if settings.VMS_VM_BACKUP_ENABLED:
    from api.vm.views import vm_define_backup_list_all

    urlpatterns += [
        # define backup report
        path('define/backup/', vm_define_backup_list_all, name='api_vm_define_backup_list_all'),
        # backup
        # /vm/<hostname_or_uuid>/backup - get, delete
        re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/backup/$', vm_backup_list, name='api_vm_backup_list'),
        # /vm/<hostname>/backup/<bkpname> - get, create, set, delete
        re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/backup/(?P<bkpname>[A-Za-z0-9\._-]+)/$',
                vm_backup, name='api_vm_backup'),
        # define backup
        # /vm/<hostname_or_uuid>/define/backup - get
        re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/define/backup/$',
                vm_define_backup_list, name='api_vm_define_backup_list'),
        # /vm/<hostname_or_uuid>/define/backup/<bkpdef> - get, create, set, delete
        re_path(r'^(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/define/backup/(?P<bkpdef>[A-Za-z0-9\._-]+)/$',
                vm_define_backup, name='api_vm_define_backup'),
    ]

if settings.MON_ZABBIX_ENABLED:
    urlpatterns += [path('', include('api.mon.vm.urls'))]
