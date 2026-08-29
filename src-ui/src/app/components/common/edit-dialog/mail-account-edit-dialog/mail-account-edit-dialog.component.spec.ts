import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import {
  IMAPSecurity,
  MailAccount,
  MailAccountType,
} from 'src/app/data/mail-account'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SettingsService } from 'src/app/services/settings.service'
import { environment } from 'src/environments/environment'
import { CheckComponent } from '../../input/check/check.component'
import { PasswordComponent } from '../../input/password/password.component'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { EditDialogMode } from '../edit-dialog.component'
import { MailAccountEditDialogComponent } from './mail-account-edit-dialog.component'

describe('MailAccountEditDialogComponent', () => {
  let component: MailAccountEditDialogComponent
  let settingsService: SettingsService
  let fixture: ComponentFixture<MailAccountEditDialogComponent>
  let httpController: HttpTestingController

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        NgbModule,
        MailAccountEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        CheckComponent,
        PermissionsFormComponent,
        PasswordComponent,
      ],
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    httpController = TestBed.inject(HttpTestingController)

    fixture = TestBed.createComponent(MailAccountEditDialogComponent)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser.set({ id: 99, username: 'user99' })
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support create and edit modes', () => {
    component.dialogMode.set(EditDialogMode.CREATE)
    const createTitleSpy = jest.spyOn(component, 'getCreateTitle')
    const editTitleSpy = jest.spyOn(component, 'getEditTitle')
    fixture.detectChanges()
    expect(createTitleSpy).toHaveBeenCalled()
    expect(editTitleSpy).not.toHaveBeenCalled()
    component.dialogMode.set(EditDialogMode.EDIT)
    fixture.detectChanges()
    expect(editTitleSpy).toHaveBeenCalled()
  })

  it('should support test mail account and show appropriate expiring alert', () => {
    jest.useFakeTimers()
    component.object = {
      name: 'example',
      imap_server: 'imap.example.com',
      username: 'user',
      password: 'pass',
      imap_port: 443,
      imap_security: IMAPSecurity.SSL,
      is_token: false,
      account_type: MailAccountType.IMAP,
    }

    // success
    component.test()
    httpController
      .expectOne(`${environment.apiBaseUrl}mail_accounts/test/`)
      .flush({ success: true })
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain(
      'Successfully connected'
    )
    jest.advanceTimersByTime(6000)
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).not.toContain(
      'Successfully connected'
    )

    // not success
    component.test()
    httpController
      .expectOne(`${environment.apiBaseUrl}mail_accounts/test/`)
      .flush({ success: false })
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain('Unable to connect')

    // error
    component.test()
    httpController
      .expectOne(`${environment.apiBaseUrl}mail_accounts/test/`)
      .flush({}, { status: 500, statusText: 'error' })
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain('Unable to connect')
    jest.advanceTimersByTime(6000)
    jest.useRealTimers()
  })

  describe('IMAP port prefill', () => {
    const createDialog = (
      mode: EditDialogMode,
      object?: MailAccount
    ): MailAccountEditDialogComponent => {
      const f = TestBed.createComponent(MailAccountEditDialogComponent)
      f.componentInstance.dialogMode.set(mode)
      if (object) {
        f.componentInstance.object = object
      }
      f.detectChanges()
      return f.componentInstance
    }

    const existingAccount = (overrides: Partial<MailAccount>): MailAccount =>
      ({
        id: 1,
        name: 'example',
        imap_server: 'imap.example.com',
        imap_port: 993,
        imap_security: IMAPSecurity.SSL,
        username: 'user',
        password: 'pass',
        is_token: false,
        account_type: MailAccountType.IMAP,
        ...overrides,
      }) as MailAccount

    it('should prefill the port with the SSL default for a new account', () => {
      const c = createDialog(EditDialogMode.CREATE)
      expect(c.objectForm.get('imap_security').value).toEqual(IMAPSecurity.SSL)
      expect(c.objectForm.get('imap_port').value).toEqual(993)
    })

    it('should update the port when the security setting changes', () => {
      const c = createDialog(EditDialogMode.CREATE)
      // Start on SSL/993, so moving to None has to change the value: landing on
      // 143 from a security setting that already defaults to it would assert
      // nothing about whether the handler ran.
      c.objectForm.get('imap_security').setValue(IMAPSecurity.None)
      expect(c.objectForm.get('imap_port').value).toEqual(143)
      // None and STARTTLS do share a default, so this transition really is a
      // no-op, and is here to pin that rather than to prove a change.
      c.objectForm.get('imap_security').setValue(IMAPSecurity.STARTTLS)
      expect(c.objectForm.get('imap_port').value).toEqual(143)
      c.objectForm.get('imap_security').setValue(IMAPSecurity.SSL)
      expect(c.objectForm.get('imap_port').value).toEqual(993)
    })

    it('should fill an empty port with the default for the new security setting', () => {
      const c = createDialog(EditDialogMode.CREATE)
      c.objectForm.get('imap_port').setValue('')
      c.objectForm.get('imap_security').setValue(IMAPSecurity.STARTTLS)
      expect(c.objectForm.get('imap_port').value).toEqual(143)
      c.objectForm.get('imap_port').setValue(null)
      c.objectForm.get('imap_security').setValue(IMAPSecurity.SSL)
      expect(c.objectForm.get('imap_port').value).toEqual(993)
    })

    it('should not clobber a port the user customised', () => {
      const c = createDialog(EditDialogMode.CREATE)
      // the port input is a text field, so a typed value arrives as a string
      c.objectForm.get('imap_port').setValue('1000')
      c.objectForm.get('imap_security').setValue(IMAPSecurity.STARTTLS)
      expect(c.objectForm.get('imap_port').value).toEqual('1000')
      c.objectForm.get('imap_security').setValue(IMAPSecurity.SSL)
      expect(c.objectForm.get('imap_port').value).toEqual('1000')
    })

    it('should not change the stored port when editing an existing account', () => {
      // 993 is the default the form starts on and STARTTLS is not, so a
      // subscription established before the base class patches the account in
      // would rewrite this to 143. A case that does not discriminate on both
      // fields passes whether the ordering is right or wrong.
      const c = createDialog(
        EditDialogMode.EDIT,
        existingAccount({
          imap_port: 993,
          imap_security: IMAPSecurity.STARTTLS,
        })
      )
      expect(c.objectForm.get('imap_port').value).toEqual(993)
    })

    it('should treat a blank port as unset rather than as customised', () => {
      const c = createDialog(EditDialogMode.CREATE)
      c.objectForm.get('imap_port').setValue('   ')
      c.objectForm.get('imap_security').setValue(IMAPSecurity.STARTTLS)
      expect(c.objectForm.get('imap_port').value).toEqual(143)
    })

    it('should keep a customised port of an existing account across a security change', () => {
      const c = createDialog(
        EditDialogMode.EDIT,
        existingAccount({ imap_port: 1000, imap_security: IMAPSecurity.SSL })
      )
      c.objectForm.get('imap_security').setValue(IMAPSecurity.STARTTLS)
      expect(c.objectForm.get('imap_port').value).toEqual(1000)
    })

    it('should update a default port of an existing account on a security change', () => {
      const c = createDialog(
        EditDialogMode.EDIT,
        existingAccount({ imap_port: 993, imap_security: IMAPSecurity.SSL })
      )
      expect(c.objectForm.get('imap_port').value).toEqual(993)
      c.objectForm.get('imap_security').setValue(IMAPSecurity.STARTTLS)
      expect(c.objectForm.get('imap_port').value).toEqual(143)
    })

    it('should not overwrite a non-default port of an existing account with unencrypted security', () => {
      const c = createDialog(
        EditDialogMode.EDIT,
        existingAccount({ imap_port: 8143, imap_security: IMAPSecurity.None })
      )
      c.objectForm.get('imap_security').setValue(IMAPSecurity.SSL)
      expect(c.objectForm.get('imap_port').value).toEqual(8143)
    })
  })
})
