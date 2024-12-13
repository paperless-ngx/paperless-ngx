import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { of } from 'rxjs'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { UserService } from 'src/app/services/rest/user.service'
import { PermissionsFormComponent } from '../input/permissions/permissions-form/permissions-form.component'
import { PermissionsGroupComponent } from '../input/permissions/permissions-group/permissions-group.component'
import { PermissionsUserComponent } from '../input/permissions/permissions-user/permissions-user.component'
import { SelectComponent } from '../input/select/select.component'
import { SwitchComponent } from '../input/switch/switch.component'
import { PermissionsDialogComponent } from './permissions-dialog.component'

const set_permissions = {
  owner: 10,
  set_permissions: {
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

describe('PermissionsDialogComponent', () => {
  let component: PermissionsDialogComponent
  let fixture: ComponentFixture<PermissionsDialogComponent>
  let modal: NgbActiveModal

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        PermissionsDialogComponent,
        SafeHtmlPipe,
        SelectComponent,
        SwitchComponent,
        PermissionsFormComponent,
        PermissionsUserComponent,
        PermissionsGroupComponent,
      ],
      imports: [NgSelectModule, FormsModule, ReactiveFormsModule, NgbModule],
      providers: [
        NgbActiveModal,
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
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    modal = TestBed.inject(NgbActiveModal)
    fixture = TestBed.createComponent(PermissionsDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should return permissions', () => {
    expect(component.permissions).toEqual({
      owner: null,
      set_permissions: {
        view: {
          users: [],
          groups: [],
        },
        change: {
          users: [],
          groups: [],
        },
      },
    })
    component.form.get('permissions_form').setValue(set_permissions)
    expect(component.permissions).toEqual(set_permissions)
  })

  it('should close modal on cancel', () => {
    const closeSpy = jest.spyOn(modal, 'close')
    component.cancelClicked()
    expect(closeSpy).toHaveBeenCalled()
  })

  it('should support edit permissions on object', () => {
    let obj = {
      id: 1,
      name: 'account1',
      owner: set_permissions.owner,
      permissions: set_permissions.set_permissions,
    }
    component.object = obj
    expect(component.title).toEqual(`Edit permissions for ${obj.name}`)
    expect(component.permissions).toEqual(set_permissions)
  })

  it('should toggle hint based on object existence (if editing) or merge flag', () => {
    component.form.get('merge').setValue(true)
    expect(component.hint.includes('Existing')).toBeTruthy()
    component.form.get('merge').setValue(false)
    expect(component.hint.includes('will be replaced')).toBeTruthy()
    component.object = {}
    expect(component.hint).toBeNull()
  })

  it('should emit permissions and merge flag on confirm', () => {
    const confirmSpy = jest.spyOn(component.confirmClicked, 'emit')
    component.form.get('permissions_form').setValue(set_permissions)
    component.confirm()
    expect(confirmSpy).toHaveBeenCalledWith({
      permissions: set_permissions,
      merge: true,
    })
  })
})
