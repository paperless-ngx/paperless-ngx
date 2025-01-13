import { TestBed } from '@angular/core/testing'
import { Document } from '../data/document'
import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from './permissions.service'

describe('PermissionsService', () => {
  let permissionsService: PermissionsService

  const docUnowned: Document = {
    title: 'Doc title',
    owner: null,
  }

  const docOwned: Document = {
    title: 'Doc title 2',
    owner: 1,
  }

  const docNotOwned: Document = {
    title: 'Doc title 3',
    owner: 2,
  }

  const docUserViewGranted: Document = {
    title: 'Doc title 4',
    owner: 2,
    permissions: {
      view: {
        users: [1],
        groups: [],
      },
      change: {
        users: [],
        groups: [],
      },
    },
  }

  const docUserEditGranted: Document = {
    title: 'Doc title 5',
    owner: 2,
    permissions: {
      view: {
        users: [1],
        groups: [],
      },
      change: {
        users: [1],
        groups: [],
      },
    },
  }

  const docGroupViewGranted: Document = {
    title: 'Doc title 4',
    owner: 2,
    permissions: {
      view: {
        users: [],
        groups: [1],
      },
      change: {
        users: [],
        groups: [],
      },
    },
  }

  const docGroupEditGranted: Document = {
    title: 'Doc title 5',
    owner: 2,
    permissions: {
      view: {
        users: [],
        groups: [1],
      },
      change: {
        users: [],
        groups: [1],
      },
    },
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [PermissionsService],
    })

    permissionsService = TestBed.inject(PermissionsService)
  })

  it('correctly interpolates action codes to keys', () => {
    expect(
      permissionsService.getPermissionCode(
        PermissionAction.View,
        PermissionType.Document
      )
    ).toEqual('view_document')
    expect(permissionsService.getPermissionKeys('view_document')).toEqual({
      actionKey: 'View', // PermissionAction.View
      typeKey: 'Document', // PermissionType.Document
    })
  })

  it('correctly checks explicit global permissions', () => {
    permissionsService.initialize(
      [
        'change_savedview',
        'change_schedule',
        'change_failure',
        'delete_token',
        'add_mailrule',
        'view_failure',
        'view_groupresult',
        'add_note',
        'change_taskresult',
        'view_tag',
        'view_user',
        'add_tag',
        'change_processedmail',
        'change_session',
        'view_taskattributes',
        'delete_groupresult',
        'delete_correspondent',
        'delete_schedule',
        'delete_contenttype',
        'view_chordcounter',
        'view_success',
        'delete_documenttype',
        'add_tokenproxy',
        'delete_paperlesstask',
        'add_log',
        'view_mailaccount',
        'add_uisettings',
        'view_savedview',
        'view_uisettings',
        'delete_storagepath',
        'delete_frontendsettings',
        'change_paperlesstask',
        'view_taskresult',
        'delete_processedmail',
        'view_processedmail',
        'view_session',
        'delete_chordcounter',
        'view_note',
        'delete_session',
        'view_document',
        'change_mailaccount',
        'delete_taskattributes',
        'add_groupobjectpermission',
        'view_mailrule',
        'change_savedviewfilterrule',
        'change_log',
        'change_comment',
        'add_mailaccount',
        'add_frontendsettings',
        'add_userobjectpermission',
        'delete_note',
        'view_token',
        'add_failure',
        'delete_user',
        'add_success',
        'view_ormq',
        'view_tokenproxy',
        'delete_uisettings',
        'change_groupobjectpermission',
        'add_logentry',
        'add_ormq',
        'view_frontendsettings',
        'view_schedule',
        'change_taskattributes',
        'view_documenttype',
        'view_logentry',
        'change_correspondent',
        'add_groupresult',
        'delete_groupobjectpermission',
        'change_mailrule',
        'change_permission',
        'delete_log',
        'view_userobjectpermission',
        'view_correspondent',
        'delete_document',
        'change_uisettings',
        'change_storagepath',
        'change_document',
        'delete_tokenproxy',
        'change_note',
        'delete_permission',
        'change_contenttype',
        'add_token',
        'change_success',
        'delete_logentry',
        'view_savedviewfilterrule',
        'delete_task',
        'add_savedview',
        'add_paperlesstask',
        'add_task',
        'change_documenttype',
        'add_documenttype',
        'change_token',
        'view_task',
        'view_permission',
        'change_task',
        'delete_userobjectpermission',
        'change_group',
        'add_group',
        'change_tag',
        'change_chordcounter',
        'add_storagepath',
        'delete_group',
        'add_taskattributes',
        'delete_mailaccount',
        'delete_tag',
        'add_schedule',
        'delete_failure',
        'delete_mailrule',
        'add_savedviewfilterrule',
        'change_ormq',
        'change_logentry',
        'add_taskresult',
        'view_group',
        'delete_comment',
        'add_contenttype',
        'add_document',
        'change_tokenproxy',
        'delete_success',
        'add_comment',
        'delete_ormq',
        'add_processedmail',
        'view_paperlesstask',
        'delete_savedview',
        'change_user',
        'add_session',
        'view_groupobjectpermission',
        'add_user',
        'add_correspondent',
        'delete_taskresult',
        'view_contenttype',
        'view_storagepath',
        'add_permission',
        'change_userobjectpermission',
        'delete_savedviewfilterrule',
        'change_groupresult',
        'add_chordcounter',
        'view_log',
        'view_comment',
        'change_frontendsettings',
        'add_sharelink',
        'view_sharelink',
        'change_sharelink',
        'delete_sharelink',
        'add_workflow',
        'view_workflow',
        'change_workflow',
        'delete_workflow',
        'add_customfield',
        'view_customfield',
        'change_customfield',
        'delete_customfield',
        'add_applicationconfiguration',
        'change_applicationconfiguration',
        'delete_applicationconfiguration',
        'view_applicationconfiguration',
      ],
      {
        username: 'testuser',
        last_name: 'User',
        first_name: 'Test',
      }
    )

    Object.values(PermissionType).forEach((type) => {
      Object.values(PermissionAction).forEach((action) => {
        expect(permissionsService.currentUserCan(action, type)).toBeTruthy()
      })
    })

    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
    })

    Object.values(PermissionType).forEach((type) => {
      Object.values(PermissionAction).forEach((action) => {
        expect(permissionsService.currentUserCan(action, type)).toBeFalsy()
      })
    })
  })

  it('correctly checks global permissions for superuser', () => {
    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
      is_superuser: true,
    })

    Object.values(PermissionType).forEach((type) => {
      Object.values(PermissionAction).forEach((action) => {
        expect(permissionsService.currentUserCan(action, type)).toBeTruthy()
      })
    })
  })

  it('correctly checks object owner permissions', () => {
    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
      id: 1,
    })

    expect(permissionsService.currentUserOwnsObject(docUnowned)).toBeTruthy()
    expect(permissionsService.currentUserOwnsObject(docOwned)).toBeTruthy()
    expect(permissionsService.currentUserOwnsObject(docNotOwned)).toBeFalsy()
  })

  it('correctly checks object owner permissions for superuser', () => {
    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
      id: 1,
      is_superuser: true,
    })

    expect(permissionsService.currentUserOwnsObject(docUnowned)).toBeTruthy()
    expect(permissionsService.currentUserOwnsObject(docOwned)).toBeTruthy()
    expect(permissionsService.currentUserOwnsObject(docNotOwned)).toBeTruthy()
  })

  it('correctly checks granted object permissions', () => {
    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
      id: 1,
    })

    expect(
      permissionsService.currentUserHasObjectPermissions(
        PermissionAction.View,
        docNotOwned
      )
    ).toBeFalsy()
    expect(
      permissionsService.currentUserHasObjectPermissions(
        PermissionAction.View,
        docUserViewGranted
      )
    ).toBeTruthy()
    expect(
      permissionsService.currentUserHasObjectPermissions(
        PermissionAction.Change,
        docUserEditGranted
      )
    ).toBeTruthy()
  })

  it('correctly checks granted object permissions for superuser', () => {
    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
      id: 1,
      is_superuser: true,
    })

    expect(
      permissionsService.currentUserHasObjectPermissions(
        PermissionAction.View,
        docNotOwned
      )
    ).toBeTruthy()
    expect(
      permissionsService.currentUserHasObjectPermissions(
        PermissionAction.View,
        docUserViewGranted
      )
    ).toBeTruthy()
    expect(
      permissionsService.currentUserHasObjectPermissions(
        PermissionAction.Change,
        docUserEditGranted
      )
    ).toBeTruthy()
  })

  it('correctly checks granted object permissions from group', () => {
    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
      id: 1,
      groups: [1],
    })

    expect(
      permissionsService.currentUserHasObjectPermissions(
        PermissionAction.View,
        docNotOwned
      )
    ).toBeFalsy()
    expect(
      permissionsService.currentUserHasObjectPermissions(
        PermissionAction.View,
        docGroupViewGranted
      )
    ).toBeTruthy()
    expect(
      permissionsService.currentUserHasObjectPermissions(
        PermissionAction.Change,
        docGroupEditGranted
      )
    ).toBeTruthy()
  })

  it('correctly checks admin status', () => {
    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
      id: 1,
      is_staff: true,
    })

    expect(permissionsService.isAdmin()).toBeTruthy()

    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
      id: 1,
    })

    expect(permissionsService.isAdmin()).toBeFalsy()
  })

  it('correctly checks superuser status', () => {
    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
      id: 1,
      is_superuser: true,
    })

    expect(permissionsService.isSuperUser()).toBeTruthy()

    permissionsService.initialize([], {
      username: 'testuser',
      last_name: 'User',
      first_name: 'Test',
      id: 1,
    })

    expect(permissionsService.isSuperUser()).toBeFalsy()
  })
})
