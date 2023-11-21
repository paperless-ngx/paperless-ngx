import { ComponentFixture, TestBed } from '@angular/core/testing'

import { ProfileEditDialogComponent } from './profile-edit-dialog.component'
import { ProfileService } from 'src/app/services/profile.service'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbActiveModal,
  NgbModal,
  NgbModalModule,
  NgbModule,
} from '@ng-bootstrap/ng-bootstrap'
import { HttpClientModule } from '@angular/common/http'
import { TextComponent } from '../input/text/text.component'
import { PasswordComponent } from '../input/password/password.component'
import { of, throwError } from 'rxjs'
import { ToastService } from 'src/app/services/toast.service'

const profile = {
  email: 'foo@bar.com',
  password: '*********',
  first_name: 'foo',
  last_name: 'bar',
}

describe('ProfileEditDialogComponent', () => {
  let component: ProfileEditDialogComponent
  let fixture: ComponentFixture<ProfileEditDialogComponent>
  let profileService: ProfileService
  let toastService: ToastService

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [
        ProfileEditDialogComponent,
        TextComponent,
        PasswordComponent,
      ],
      providers: [NgbActiveModal],
      imports: [
        HttpClientModule,
        ReactiveFormsModule,
        FormsModule,
        NgbModalModule,
      ],
    })
    profileService = TestBed.inject(ProfileService)
    toastService = TestBed.inject(ToastService)
    fixture = TestBed.createComponent(ProfileEditDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should get profile on init, display in form', () => {
    const getSpy = jest.spyOn(profileService, 'get')
    getSpy.mockReturnValue(of(profile))
    component.ngOnInit()
    expect(getSpy).toHaveBeenCalled()
    fixture.detectChanges()
    expect(component.form.get('email').value).toEqual(profile.email)
  })

  it('should update profile on save, display error if needed', () => {
    const newProfile = {
      email: 'foo@bar2.com',
      password: profile.password,
      first_name: 'foo2',
      last_name: profile.last_name,
    }
    const updateSpy = jest.spyOn(profileService, 'update')
    const errorSpy = jest.spyOn(toastService, 'showError')
    updateSpy.mockReturnValueOnce(throwError(() => new Error('failed to save')))
    component.save()
    expect(errorSpy).toHaveBeenCalled()

    updateSpy.mockClear()
    const infoSpy = jest.spyOn(toastService, 'showInfo')
    component.form.patchValue(newProfile)
    updateSpy.mockReturnValueOnce(of(newProfile))
    component.save()
    expect(updateSpy).toHaveBeenCalledWith(newProfile)
    expect(infoSpy).toHaveBeenCalled()
  })

  it('should close on cancel', () => {
    const closeSpy = jest.spyOn(component.activeModal, 'close')
    component.cancel()
    expect(closeSpy).toHaveBeenCalled()
  })
})
