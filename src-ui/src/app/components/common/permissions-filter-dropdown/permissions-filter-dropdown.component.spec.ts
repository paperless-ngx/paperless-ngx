import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ClearableBadgeComponent } from '../clearable-badge/clearable-badge.component'
import {
  OwnerFilterType,
  PermissionsFilterDropdownComponent,
  PermissionsSelectionModel,
} from './permissions-filter-dropdown.component'

const currentUserID = 13

describe('PermissionsFilterDropdownComponent', () => {
  let component: PermissionsFilterDropdownComponent
  let fixture: ComponentFixture<PermissionsFilterDropdownComponent>
  let ownerFilterSetResult: PermissionsSelectionModel

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgSelectModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
        PermissionsFilterDropdownComponent,
        ClearableBadgeComponent,
        IfPermissionsDirective,
      ],
      providers: [
        {
          provide: UserService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 1,
                    username: 'user1',
                  },
                  {
                    id: 10,
                    username: 'user10',
                  },
                ],
              }),
          },
        },
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
          },
        },
        {
          provide: SettingsService,
          useValue: {
            currentUser: () => ({
              id: currentUserID,
            }),
          },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(PermissionsFilterDropdownComponent)
    component = fixture.componentInstance
    component.ownerFilterSet.subscribe(
      (model) => (ownerFilterSetResult = model)
    )
    component.selectionModel = new PermissionsSelectionModel()

    fixture.detectChanges()
  })

  it('should report is active', () => {
    component.setFilter(OwnerFilterType.NONE)
    expect(component.isActive).toBeFalsy()
    component.setFilter(OwnerFilterType.OTHERS)
    expect(component.isActive).toBeTruthy()
    component.setFilter(OwnerFilterType.NONE)
    component.selectionModel.hideUnowned.set(true)
    expect(component.isActive).toBeTruthy()
  })

  it('should describe concrete user filters honestly', () => {
    component.selectionModel.ownerFilter.set(OwnerFilterType.SELF)
    component.selectionModel.userID.set(1)
    expect(component.ownerFilterLabel).toEqual('Owned by user1')

    component.selectionModel.ownerFilter.set(OwnerFilterType.NOT_SELF)
    component.selectionModel.excludeUsers.set([1])
    expect(component.ownerExclusionFilterLabel).toEqual('Not owned by user1')

    component.selectionModel.ownerFilter.set(OwnerFilterType.SHARED_BY_ME)
    component.selectionModel.userID.set(1)
    expect(component.sharedByFilterLabel).toEqual('Shared by user1')
  })

  it('should describe concrete filters when usernames are unavailable', () => {
    component.selectionModel.ownerFilter.set(OwnerFilterType.SELF)
    component.selectionModel.userID.set(99)
    expect(component.ownerFilterLabel).toEqual('Owned by another user')

    component.selectionModel.ownerFilter.set(OwnerFilterType.NOT_SELF)
    component.selectionModel.excludeUsers.set([99])
    expect(component.ownerExclusionFilterLabel).toEqual(
      'Not owned by another user'
    )

    component.selectionModel.excludeUsers.set([98, 99])
    expect(component.ownerExclusionFilterLabel).toEqual(
      'Not owned by selected users'
    )

    component.selectionModel.ownerFilter.set(OwnerFilterType.SHARED_BY_ME)
    component.selectionModel.userID.set(99)
    expect(component.sharedByFilterLabel).toEqual('Shared by another user')
  })

  it('should retain relative labels for filters bound to the current user', () => {
    component.selectionModel.userID.set(currentUserID)
    expect(component.ownerFilterLabel).toEqual('My documents')
    expect(component.sharedByFilterLabel).toEqual('Shared by me')

    component.selectionModel.excludeUsers.set([currentUserID])
    expect(component.ownerExclusionFilterLabel).toEqual('Shared with me')
  })

  it('should retain relative labels for inactive filter choices', () => {
    component.selectionModel.ownerFilter.set(OwnerFilterType.NONE)

    expect(component.ownerFilterLabel).toEqual('My documents')
    expect(component.ownerExclusionFilterLabel).toEqual('Shared with me')
    expect(component.sharedByFilterLabel).toEqual('Shared by me')
  })

  it('should support reset', () => {
    component.setFilter(OwnerFilterType.OTHERS)
    expect(component.selectionModel.ownerFilter()).not.toEqual(
      OwnerFilterType.NONE
    )
    component.reset()
    expect(component.selectionModel.ownerFilter()).toEqual(OwnerFilterType.NONE)
  })

  it('should toggle owner filter type when users selected', () => {
    component.selectionModel.ownerFilter.set(OwnerFilterType.NONE)

    // this would normally be done by select component
    component.selectionModel.includeUsers.set([12])
    component.onUserSelect()
    expect(component.selectionModel.ownerFilter()).toEqual(
      OwnerFilterType.OTHERS
    )

    // this would normally be done by select component
    component.selectionModel.includeUsers.set(null)
    component.onUserSelect()

    expect(component.selectionModel.ownerFilter()).toEqual(OwnerFilterType.NONE)
  })
  it('should clear selected users', () => {
    component.selectionModel.includeUsers.set([12])
    component.onUserSelect()
    component.selectionModel.hideUnowned.set(true)
    expect(component.selectionModel.ownerFilter()).toEqual(
      OwnerFilterType.OTHERS
    )

    component.clearIncludeUsers()

    expect(component.selectionModel.includeUsers()).toEqual([])
    expect(component.selectionModel.ownerFilter()).toEqual(OwnerFilterType.NONE)
    expect(component.selectionModel.hideUnowned()).toBeTruthy()
  })

  it('should emit a selection model depending on the type of owner filter set', () => {
    const emitted = () => ({
      excludeUsers: ownerFilterSetResult.excludeUsers(),
      hideUnowned: ownerFilterSetResult.hideUnowned(),
      includeUsers: ownerFilterSetResult.includeUsers(),
      ownerFilter: ownerFilterSetResult.ownerFilter(),
      userID: ownerFilterSetResult.userID(),
    })
    component.selectionModel.ownerFilter.set(OwnerFilterType.NONE)

    component.setFilter(OwnerFilterType.SELF)
    expect(emitted()).toEqual({
      excludeUsers: [],
      hideUnowned: false,
      includeUsers: [],
      ownerFilter: OwnerFilterType.SELF,
      userID: currentUserID,
    })

    component.setFilter(OwnerFilterType.NOT_SELF)
    expect(emitted()).toEqual({
      excludeUsers: [currentUserID],
      hideUnowned: false,
      includeUsers: [],
      ownerFilter: OwnerFilterType.NOT_SELF,
      userID: null,
    })

    component.setFilter(OwnerFilterType.NONE)
    expect(emitted()).toEqual({
      excludeUsers: [],
      hideUnowned: false,
      includeUsers: [],
      ownerFilter: OwnerFilterType.NONE,
      userID: null,
    })

    component.setFilter(OwnerFilterType.SHARED_BY_ME)
    expect(emitted()).toEqual({
      excludeUsers: [],
      hideUnowned: false,
      includeUsers: [],
      ownerFilter: OwnerFilterType.SHARED_BY_ME,
      userID: currentUserID,
    })

    component.setFilter(OwnerFilterType.UNOWNED)
    expect(emitted()).toEqual({
      excludeUsers: [],
      hideUnowned: false,
      includeUsers: [],
      ownerFilter: OwnerFilterType.UNOWNED,
      userID: null,
    })
  })
})
