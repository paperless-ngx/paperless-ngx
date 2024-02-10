import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'

import { ProfileEditDialogComponent } from './profile-edit-dialog.component'
import { ProfileService } from 'src/app/services/profile.service'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbAccordionModule,
  NgbActiveModal,
  NgbModalModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { HttpClientModule } from '@angular/common/http'
import { TextComponent } from '../input/text/text.component'
import { PasswordComponent } from '../input/password/password.component'
import { of, throwError } from 'rxjs'
import { ToastService } from 'src/app/services/toast.service'
import { Clipboard } from '@angular/cdk/clipboard'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { ConfirmButtonComponent } from '../confirm-button/confirm-button.component'

const socialAccount = {
  id: 1,
  provider: 'test_provider',
  name: 'Test Provider',
}
const profile = {
  email: 'foo@bar.com',
  password: '*********',
  first_name: 'foo',
  last_name: 'bar',
  auth_token: '123456789abcdef',
  social_accounts: [socialAccount],
}
const socialAccountProviders = [
  { name: 'Test Provider', login_url: 'https://example.com' },
]

describe('ProfileEditDialogComponent', () => {
  let component: ProfileEditDialogComponent
  let fixture: ComponentFixture<ProfileEditDialogComponent>
  let profileService: ProfileService
  let toastService: ToastService
  let clipboard: Clipboard

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [
        ProfileEditDialogComponent,
        TextComponent,
        PasswordComponent,
        ConfirmButtonComponent,
      ],
      providers: [NgbActiveModal],
      imports: [
        HttpClientModule,
        ReactiveFormsModule,
        FormsModule,
        NgbModalModule,
        NgbAccordionModule,
        NgxBootstrapIconsModule.pick(allIcons),
        NgbPopoverModule,
      ],
    })
    profileService = TestBed.inject(ProfileService)
    toastService = TestBed.inject(ToastService)
    clipboard = TestBed.inject(Clipboard)
    fixture = TestBed.createComponent(ProfileEditDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should get profile on init, display in form', () => {
    const getSpy = jest.spyOn(profileService, 'get')
    getSpy.mockReturnValue(of(profile))
    const getProvidersSpy = jest.spyOn(
      profileService,
      'getSocialAccountProviders'
    )
    getProvidersSpy.mockReturnValue(of(socialAccountProviders))
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
      auth_token: profile.auth_token,
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

  it('should show additional confirmation field when email changes, warn with error & disable save', () => {
    expect(component.form.get('email_confirm').enabled).toBeFalsy()
    const getSpy = jest.spyOn(profileService, 'get')
    getSpy.mockReturnValue(of(profile))
    const getProvidersSpy = jest.spyOn(
      profileService,
      'getSocialAccountProviders'
    )
    getProvidersSpy.mockReturnValue(of(socialAccountProviders))
    component.ngOnInit()
    component.form.get('email').patchValue('foo@bar2.com')
    component.onEmailKeyUp({ target: { value: 'foo@bar2.com' } } as any)
    fixture.detectChanges()
    expect(component.form.get('email_confirm').enabled).toBeTruthy()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      'Emails must match'
    )
    expect(component.saveDisabled).toBeTruthy()

    component.form.get('email_confirm').patchValue('foo@bar2.com')
    component.onEmailConfirmKeyUp({ target: { value: 'foo@bar2.com' } } as any)
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).not.toContain(
      'Emails must match'
    )
    expect(component.saveDisabled).toBeFalsy()

    component.form.get('email').patchValue(profile.email)
    fixture.detectChanges()
    expect(component.form.get('email_confirm').enabled).toBeFalsy()
    expect(fixture.debugElement.nativeElement.textContent).not.toContain(
      'Emails must match'
    )
    expect(component.saveDisabled).toBeFalsy()
  })

  it('should show additional confirmation field when password changes, warn with error & disable save', () => {
    expect(component.form.get('password_confirm').enabled).toBeFalsy()
    const getSpy = jest.spyOn(profileService, 'get')
    getSpy.mockReturnValue(of(profile))
    const getProvidersSpy = jest.spyOn(
      profileService,
      'getSocialAccountProviders'
    )
    getProvidersSpy.mockReturnValue(of(socialAccountProviders))
    component.hasUsablePassword = true
    component.ngOnInit()
    component.form.get('password').patchValue('new*pass')
    component.onPasswordKeyUp({
      target: { value: 'new*pass', tagName: 'input' },
    } as any)
    component.onPasswordKeyUp({ target: { tagName: 'button' } } as any) // coverage
    fixture.detectChanges()
    expect(component.form.get('password_confirm').enabled).toBeTruthy()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      'Passwords must match'
    )
    expect(component.saveDisabled).toBeTruthy()

    component.form.get('password_confirm').patchValue('new*pass')
    component.onPasswordConfirmKeyUp({ target: { value: 'new*pass' } } as any)
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).not.toContain(
      'Passwords must match'
    )
    expect(component.saveDisabled).toBeFalsy()

    component.form.get('password').patchValue(profile.password)
    fixture.detectChanges()
    expect(component.form.get('password_confirm').enabled).toBeFalsy()
    expect(fixture.debugElement.nativeElement.textContent).not.toContain(
      'Passwords must match'
    )
    expect(component.saveDisabled).toBeFalsy()
  })

  it('should logout on save if password changed', fakeAsync(() => {
    const getSpy = jest.spyOn(profileService, 'get')
    getSpy.mockReturnValue(of(profile))
    const getProvidersSpy = jest.spyOn(
      profileService,
      'getSocialAccountProviders'
    )
    getProvidersSpy.mockReturnValue(of(socialAccountProviders))
    component.ngOnInit()
    component['newPassword'] = 'new*pass'
    component.form.get('password').patchValue('new*pass')
    component.form.get('password_confirm').patchValue('new*pass')

    const updateSpy = jest.spyOn(profileService, 'update')
    updateSpy.mockReturnValue(of(null))
    Object.defineProperty(window, 'location', {
      value: {
        href: 'http://localhost/',
      },
      writable: true, // possibility to override
    })
    component.save()
    expect(updateSpy).toHaveBeenCalled()
    tick(2600)
    expect(window.location.href).toContain('logout')
  }))

  it('should support auth token copy', fakeAsync(() => {
    const getSpy = jest.spyOn(profileService, 'get')
    getSpy.mockReturnValue(of(profile))
    const getProvidersSpy = jest.spyOn(
      profileService,
      'getSocialAccountProviders'
    )
    getProvidersSpy.mockReturnValue(of(socialAccountProviders))
    component.ngOnInit()
    const copySpy = jest.spyOn(clipboard, 'copy')
    component.copyAuthToken()
    expect(copySpy).toHaveBeenCalledWith(profile.auth_token)
    expect(component.copied).toBeTruthy()
    tick(3000)
    expect(component.copied).toBeFalsy()
  }))

  it('should support generate token, display error if needed', () => {
    const getSpy = jest.spyOn(profileService, 'get')
    getSpy.mockReturnValue(of(profile))

    const generateSpy = jest.spyOn(profileService, 'generateAuthToken')
    const errorSpy = jest.spyOn(toastService, 'showError')
    generateSpy.mockReturnValueOnce(
      throwError(() => new Error('failed to generate'))
    )
    component.generateAuthToken()
    expect(errorSpy).toHaveBeenCalled()

    generateSpy.mockClear()
    const newToken = '789101112hijk'
    generateSpy.mockReturnValueOnce(of(newToken))
    component.generateAuthToken()
    expect(generateSpy).toHaveBeenCalled()
    expect(component.form.get('auth_token').value).not.toEqual(
      profile.auth_token
    )
    expect(component.form.get('auth_token').value).toEqual(newToken)
  })

  it('should get social account providers on init', () => {
    const getSpy = jest.spyOn(profileService, 'get')
    getSpy.mockReturnValue(of(profile))
    const getProvidersSpy = jest.spyOn(
      profileService,
      'getSocialAccountProviders'
    )
    getProvidersSpy.mockReturnValue(of(socialAccountProviders))
    component.ngOnInit()
    expect(getProvidersSpy).toHaveBeenCalled()
  })

  it('should remove disconnected social account from component, show error if needed', () => {
    const disconnectSpy = jest.spyOn(profileService, 'disconnectSocialAccount')
    const getSpy = jest.spyOn(profileService, 'get')
    getSpy.mockImplementation(() => of(profile))
    component.ngOnInit()

    const errorSpy = jest.spyOn(toastService, 'showError')

    expect(component.socialAccounts).toContainEqual(socialAccount)

    // fail first
    disconnectSpy.mockReturnValueOnce(
      throwError(() => new Error('unable to disconnect'))
    )
    component.disconnectSocialAccount(socialAccount.id)
    expect(errorSpy).toHaveBeenCalled()

    // succeed
    disconnectSpy.mockReturnValue(of(socialAccount.id))
    component.disconnectSocialAccount(socialAccount.id)
    expect(disconnectSpy).toHaveBeenCalled()
    expect(component.socialAccounts).not.toContainEqual(socialAccount)
  })
})
