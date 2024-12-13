import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'

import { Clipboard } from '@angular/cdk/clipboard'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbAccordionModule,
  NgbActiveModal,
  NgbModalModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { ProfileService } from 'src/app/services/profile.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmButtonComponent } from '../confirm-button/confirm-button.component'
import { PasswordComponent } from '../input/password/password.component'
import { TextComponent } from '../input/text/text.component'
import { ProfileEditDialogComponent } from './profile-edit-dialog.component'

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
      imports: [
        ReactiveFormsModule,
        FormsModule,
        NgbModalModule,
        NgbAccordionModule,
        NgxBootstrapIconsModule.pick(allIcons),
        NgbPopoverModule,
      ],
      providers: [NgbActiveModal, provideHttpClient(withInterceptorsFromDi())],
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

  it('should get totp settings', () => {
    const settings = {
      url: 'http://localhost/',
      qr_svg: 'svg',
      secret: 'secret',
    }
    const getSpy = jest.spyOn(profileService, 'getTotpSettings')
    const toastSpy = jest.spyOn(toastService, 'showError')
    getSpy.mockReturnValueOnce(
      throwError(() => new Error('failed to get settings'))
    )
    component.gettotpSettings()
    expect(getSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalled()

    getSpy.mockReturnValue(of(settings))
    component.gettotpSettings()
    expect(getSpy).toHaveBeenCalled()
    expect(component.totpSettings).toEqual(settings)
  })

  it('should activate totp', () => {
    const activateSpy = jest.spyOn(profileService, 'activateTotp')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const error = new Error('failed to activate totp')
    activateSpy.mockReturnValueOnce(throwError(() => error))
    component.totpSettings = {
      url: 'http://localhost/',
      qr_svg: 'svg',
      secret: 'secret',
    }
    component.form.get('totp_code').patchValue('123456')
    component.activateTotp()
    expect(activateSpy).toHaveBeenCalledWith(
      component.totpSettings.secret,
      component.form.get('totp_code').value
    )
    expect(toastErrorSpy).toHaveBeenCalled()

    activateSpy.mockReturnValueOnce(of({ success: false, recovery_codes: [] }))
    component.activateTotp()
    expect(toastErrorSpy).toHaveBeenCalledWith('Error activating TOTP', error)

    activateSpy.mockReturnValueOnce(
      of({ success: true, recovery_codes: ['1', '2', '3'] })
    )
    component.activateTotp()
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(component.isTotpEnabled).toBeTruthy()
    expect(component.recoveryCodes).toEqual(['1', '2', '3'])
  })

  it('should deactivate totp', () => {
    const deactivateSpy = jest.spyOn(profileService, 'deactivateTotp')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const error = new Error('failed to deactivate totp')
    deactivateSpy.mockReturnValueOnce(throwError(() => error))
    component.deactivateTotp()
    expect(deactivateSpy).toHaveBeenCalled()
    expect(toastErrorSpy).toHaveBeenCalled()

    deactivateSpy.mockReturnValueOnce(of(false))
    component.deactivateTotp()
    expect(toastErrorSpy).toHaveBeenCalledWith('Error deactivating TOTP', error)

    deactivateSpy.mockReturnValueOnce(of(true))
    component.deactivateTotp()
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(component.isTotpEnabled).toBeFalsy()
  })

  it('should copy recovery codes', fakeAsync(() => {
    const copySpy = jest.spyOn(clipboard, 'copy')
    component.recoveryCodes = ['1', '2', '3']
    component.copyRecoveryCodes()
    expect(copySpy).toHaveBeenCalledWith('1\n2\n3')
    tick(3000)
  }))
})
