import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  AbstractControl,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { GroupService } from 'src/app/services/rest/group.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { PasswordComponent } from '../../input/password/password.component'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { PermissionsSelectComponent } from '../../permissions-select/permissions-select.component'
import { EditDialogMode } from '../edit-dialog.component'
import { UserEditDialogComponent } from './user-edit-dialog.component'

describe('UserEditDialogComponent', () => {
  let component: UserEditDialogComponent
  let settingsService: SettingsService
  let permissionsService: PermissionsService
  let toastService: ToastService
  let fixture: ComponentFixture<UserEditDialogComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        UserEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        PasswordComponent,
        PermissionsFormComponent,
        PermissionsSelectComponent,
      ],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        NgbActiveModal,
        {
          provide: GroupService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 1,
                    permissions: ['dummy_perms'],
                  },
                ],
              }),
          },
        },
        SettingsService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(UserEditDialogComponent)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = { id: 99, username: 'user99' }
    permissionsService = TestBed.inject(PermissionsService)
    toastService = TestBed.inject(ToastService)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support create and edit modes', () => {
    component.dialogMode = EditDialogMode.CREATE
    const createTitleSpy = jest.spyOn(component, 'getCreateTitle')
    const editTitleSpy = jest.spyOn(component, 'getEditTitle')
    fixture.detectChanges()
    expect(createTitleSpy).toHaveBeenCalled()
    expect(editTitleSpy).not.toHaveBeenCalled()
    component.dialogMode = EditDialogMode.EDIT
    fixture.detectChanges()
    expect(editTitleSpy).toHaveBeenCalled()
  })

  it('should disable user permissions select on toggle superuser', () => {
    const control: AbstractControl =
      component.objectForm.get('user_permissions')
    expect(control.disabled).toBeFalsy()
    component.objectForm.get('is_superuser').setValue(true)
    component.onToggleSuperUser()
    expect(control.disabled).toBeTruthy()
  })

  it('should update inherited permissions', () => {
    component.objectForm.get('groups').setValue(null)
    expect(component.inheritedPermissions).toEqual([])
    component.objectForm.get('groups').setValue([1])
    expect(component.inheritedPermissions).toEqual(['dummy_perms'])
    component.objectForm.get('groups').setValue([2])
    expect(component.inheritedPermissions).toEqual([])
  })

  it('should detect whether password was changed in form on save', () => {
    component.objectForm.get('password').setValue(null)
    component.save()
    expect(component.passwordIsSet).toBeFalsy()

    // unchanged pw
    component.objectForm.get('password').setValue('*******')
    component.save()
    expect(component.passwordIsSet).toBeFalsy()

    // unchanged pw
    component.objectForm.get('password').setValue('helloworld')
    component.save()
    expect(component.passwordIsSet).toBeTruthy()
  })

  it('should support deactivation of TOTP', () => {
    component.object = { id: 99, username: 'user99' }
    const deactivateSpy = jest.spyOn(
      component['service'] as UserService,
      'deactivateTotp'
    )
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    deactivateSpy.mockReturnValueOnce(throwError(() => new Error('error')))
    component.deactivateTotp()
    expect(deactivateSpy).toHaveBeenCalled()
    expect(toastErrorSpy).toHaveBeenCalled()

    deactivateSpy.mockReturnValueOnce(of(false))
    component.deactivateTotp()
    expect(deactivateSpy).toHaveBeenCalled()
    expect(toastErrorSpy).toHaveBeenCalled()

    deactivateSpy.mockReturnValueOnce(of(true))
    component.deactivateTotp()
    expect(deactivateSpy).toHaveBeenCalled()
    expect(toastInfoSpy).toHaveBeenCalled()
  })

  it('should check superuser status of current user', () => {
    expect(component.currentUserIsSuperUser).toBeFalsy()
    permissionsService.initialize([], {
      id: 99,
      username: 'user99',
      is_superuser: true,
    })
    expect(component.currentUserIsSuperUser).toBeTruthy()
  })
})
