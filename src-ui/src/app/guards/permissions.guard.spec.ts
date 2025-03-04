import { TestBed } from '@angular/core/testing'
import { ActivatedRoute, RouterState } from '@angular/router'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'
import { NotificationService } from '../services/notification.service'
import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from '../services/permissions.service'
import { PermissionsGuard } from './permissions.guard'

describe('PermissionsGuard', () => {
  let guard: PermissionsGuard
  let permissionsService: PermissionsService
  let route: ActivatedRoute
  let routerState: RouterState
  let tourService: TourService
  let notificationService: NotificationService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        PermissionsGuard,
        PermissionsService,
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              data: {
                requiredPermission: {
                  action: PermissionAction.View,
                  type: PermissionType.Document,
                },
              },
            },
          },
        },
        {
          provide: RouterState,
          useValue: {
            snapshot: {
              url: '/documents',
            },
          },
        },
        TourService,
        NotificationService,
      ],
    })

    permissionsService = TestBed.inject(PermissionsService)
    tourService = TestBed.inject(TourService)
    notificationService = TestBed.inject(NotificationService)
    guard = TestBed.inject(PermissionsGuard)
    route = TestBed.inject(ActivatedRoute)
    routerState = TestBed.inject(RouterState)
  })

  it('should activate if user has permissions', () => {
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation((action, type) => {
        return true
      })

    const canActivate = guard.canActivate(route.snapshot, routerState.snapshot)

    expect(canActivate).toBeTruthy()
  })

  it('should not activate if user does not have permissions', () => {
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation((action, type) => {
        return false
      })

    const canActivate = guard.canActivate(route.snapshot, routerState.snapshot)

    expect(canActivate).toHaveProperty('root') // returns UrlTree
  })

  it('should not activate if user does not have permissions and tour is running', () => {
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation((action, type) => {
        return false
      })
    jest.spyOn(tourService, 'getStatus').mockImplementation(() => 2)

    const notificationSpy = jest.spyOn(notificationService, 'showError')

    const canActivate = guard.canActivate(route.snapshot, routerState.snapshot)

    expect(canActivate).toHaveProperty('root') // returns UrlTree
    expect(notificationSpy).toHaveBeenCalled()
  })
})
