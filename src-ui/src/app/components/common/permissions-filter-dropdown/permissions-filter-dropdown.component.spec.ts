import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { of } from 'rxjs'
import { PermissionsService } from 'src/app/services/permissions.service'
import { UserService } from 'src/app/services/rest/user.service'
import {
  OwnerFilterType,
  PermissionsFilterDropdownComponent,
  PermissionsSelectionModel,
} from './permissions-filter-dropdown.component'
import { ClearableBadgeComponent } from '../clearable-badge/clearable-badge.component'
import { SettingsService } from 'src/app/services/settings.service'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

const currentUserID = 13

describe('PermissionsFilterDropdownComponent', () => {
  let component: PermissionsFilterDropdownComponent
  let fixture: ComponentFixture<PermissionsFilterDropdownComponent>
  let ownerFilterSetResult: PermissionsSelectionModel

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        PermissionsFilterDropdownComponent,
        ClearableBadgeComponent,
        IfPermissionsDirective,
      ],
      imports: [
        NgSelectModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
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
            currentUser: {
              id: currentUserID,
            },
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
    component.selectionModel.hideUnowned = true
    expect(component.isActive).toBeTruthy()
  })

  it('should support reset', () => {
    component.setFilter(OwnerFilterType.OTHERS)
    expect(component.selectionModel.ownerFilter).not.toEqual(
      OwnerFilterType.NONE
    )
    component.reset()
    expect(component.selectionModel.ownerFilter).toEqual(OwnerFilterType.NONE)
  })

  it('should toggle owner filter type when users selected', () => {
    component.selectionModel.ownerFilter = OwnerFilterType.NONE

    // this would normally be done by select component
    component.selectionModel.includeUsers = [12]
    component.onUserSelect()
    expect(component.selectionModel.ownerFilter).toEqual(OwnerFilterType.OTHERS)

    // this would normally be done by select component
    component.selectionModel.includeUsers = null
    component.onUserSelect()

    expect(component.selectionModel.ownerFilter).toEqual(OwnerFilterType.NONE)
  })
  it('should emit a selection model depending on the type of owner filter set', () => {
    component.selectionModel.ownerFilter = OwnerFilterType.NONE

    component.setFilter(OwnerFilterType.SELF)
    expect(ownerFilterSetResult).toEqual({
      excludeUsers: [],
      hideUnowned: false,
      includeUsers: [],
      ownerFilter: OwnerFilterType.SELF,
      userID: currentUserID,
    })

    component.setFilter(OwnerFilterType.NOT_SELF)
    expect(ownerFilterSetResult).toEqual({
      excludeUsers: [currentUserID],
      hideUnowned: false,
      includeUsers: [],
      ownerFilter: OwnerFilterType.NOT_SELF,
      userID: null,
    })

    component.setFilter(OwnerFilterType.NONE)
    expect(ownerFilterSetResult).toEqual({
      excludeUsers: [],
      hideUnowned: false,
      includeUsers: [],
      ownerFilter: OwnerFilterType.NONE,
      userID: null,
    })

    component.setFilter(OwnerFilterType.SHARED_BY_ME)
    expect(ownerFilterSetResult).toEqual({
      excludeUsers: [],
      hideUnowned: false,
      includeUsers: [],
      ownerFilter: OwnerFilterType.SHARED_BY_ME,
      userID: currentUserID,
    })

    component.setFilter(OwnerFilterType.UNOWNED)
    expect(ownerFilterSetResult).toEqual({
      excludeUsers: [],
      hideUnowned: false,
      includeUsers: [],
      ownerFilter: OwnerFilterType.UNOWNED,
      userID: null,
    })
  })
})
