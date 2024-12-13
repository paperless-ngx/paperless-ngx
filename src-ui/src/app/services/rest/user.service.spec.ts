import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'
import { UserService } from './user.service'

let httpTestingController: HttpTestingController
let service: UserService
let subscription: Subscription
const endpoint = 'users'
const user = {
  username: 'username',
  id: 1,
  user_permissions: [
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
  ],
}

// run common tests
commonAbstractNameFilterPaperlessServiceTests(endpoint, UserService)

describe('Additional service tests for UserService', () => {
  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(UserService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('should retain permissions on update', () => {
    subscription = service.listAll().subscribe()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    req.flush({
      results: [user],
    })
    subscription.unsubscribe()

    subscription = service.update(user).subscribe()
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${user.id}/`
    )
    expect(req.request.body.user_permissions).toHaveLength(
      user.user_permissions.length
    )
  })

  it('should deactivate totp', () => {
    subscription = service.deactivateTotp(user).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${user.id}/deactivate_totp/`
    )
    expect(req.request.method).toEqual('POST')
  })
})
