import { ViewportScroller, DatePipe } from '@angular/common'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { Router, ActivatedRoute, convertToParamMap } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import {
  NgbModal,
  NgbModule,
  NgbNavLink,
  NgbModalRef,
  NgbAlertModule,
} from '@ng-bootstrap/ng-bootstrap'
import { of, throwError } from 'rxjs'
import { routes } from 'src/app/app-routing.module'
import { PaperlessMailAccount } from 'src/app/data/paperless-mail-account'
import { PaperlessMailRule } from 'src/app/data/paperless-mail-rule'
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view'
import { SETTINGS_KEYS } from 'src/app/data/paperless-uisettings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { PermissionsService } from 'src/app/services/permissions.service'
import { GroupService } from 'src/app/services/rest/group.service'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService, Toast } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { GroupEditDialogComponent } from '../../common/edit-dialog/group-edit-dialog/group-edit-dialog.component'
import { MailAccountEditDialogComponent } from '../../common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component'
import { MailRuleEditDialogComponent } from '../../common/edit-dialog/mail-rule-edit-dialog/mail-rule-edit-dialog.component'
import { UserEditDialogComponent } from '../../common/edit-dialog/user-edit-dialog/user-edit-dialog.component'
import { CheckComponent } from '../../common/input/check/check.component'
import { ColorComponent } from '../../common/input/color/color.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { SettingsComponent } from './settings.component'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { SelectComponent } from '../../common/input/select/select.component'
import { TextComponent } from '../../common/input/text/text.component'
import { PasswordComponent } from '../../common/input/password/password.component'
import { NumberComponent } from '../../common/input/number/number.component'
import { TagsComponent } from '../../common/input/tags/tags.component'
import { NgSelectModule } from '@ng-select/ng-select'

const savedViews = [
  { id: 1, name: 'view1' },
  { id: 2, name: 'view2' },
]
const users = [
  { id: 1, username: 'user1', is_superuser: false },
  { id: 2, username: 'user2', is_superuser: false },
]
const groups = [
  { id: 1, name: 'group1' },
  { id: 2, name: 'group2' },
]
const mailAccounts = [
  { id: 1, name: 'account1' },
  { id: 2, name: 'account2' },
]
const mailRules = [
  { id: 1, name: 'rule1', owner: 1 },
  { id: 2, name: 'rule2', owner: 2 },
]

describe('SettingsComponent', () => {
  let component: SettingsComponent
  let fixture: ComponentFixture<SettingsComponent>
  let modalService: NgbModal
  let router: Router
  let settingsService: SettingsService
  let savedViewService: SavedViewService
  let activatedRoute: ActivatedRoute
  let viewportScroller: ViewportScroller
  let toastService: ToastService
  let userService: UserService
  let permissionsService: PermissionsService
  let groupService: GroupService
  let mailAccountService: MailAccountService
  let mailRuleService: MailRuleService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        SettingsComponent,
        PageHeaderComponent,
        IfPermissionsDirective,
        CustomDatePipe,
        ConfirmDialogComponent,
        CheckComponent,
        ColorComponent,
        SafeHtmlPipe,
        SelectComponent,
        TextComponent,
        PasswordComponent,
        NumberComponent,
        TagsComponent,
        MailAccountEditDialogComponent,
        MailRuleEditDialogComponent,
      ],
      providers: [CustomDatePipe, DatePipe, PermissionsGuard],
      imports: [
        NgbModule,
        HttpClientTestingModule,
        RouterTestingModule.withRoutes(routes),
        FormsModule,
        ReactiveFormsModule,
        NgbAlertModule,
        NgSelectModule,
      ],
    }).compileComponents()

    modalService = TestBed.inject(NgbModal)
    router = TestBed.inject(Router)
    activatedRoute = TestBed.inject(ActivatedRoute)
    viewportScroller = TestBed.inject(ViewportScroller)
    toastService = TestBed.inject(ToastService)
    settingsService = TestBed.inject(SettingsService)
    userService = TestBed.inject(UserService)
    permissionsService = TestBed.inject(PermissionsService)
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    jest
      .spyOn(permissionsService, 'currentUserOwnsObject')
      .mockReturnValue(true)
    groupService = TestBed.inject(GroupService)
    savedViewService = TestBed.inject(SavedViewService)
    mailAccountService = TestBed.inject(MailAccountService)
    mailRuleService = TestBed.inject(MailRuleService)
  })

  function completeSetup(excludeService = null) {
    if (excludeService !== userService) {
      jest.spyOn(userService, 'listAll').mockReturnValue(
        of({
          all: users.map((u) => u.id),
          count: users.length,
          results: users.concat([]),
        })
      )
    }
    if (excludeService !== groupService) {
      jest.spyOn(groupService, 'listAll').mockReturnValue(
        of({
          all: groups.map((g) => g.id),
          count: groups.length,
          results: groups.concat([]),
        })
      )
    }
    if (excludeService !== savedViewService) {
      jest.spyOn(savedViewService, 'listAll').mockReturnValue(
        of({
          all: savedViews.map((v) => v.id),
          count: savedViews.length,
          results: (savedViews as PaperlessSavedView[]).concat([]),
        })
      )
    }
    if (excludeService !== mailAccountService) {
      jest.spyOn(mailAccountService, 'listAll').mockReturnValue(
        of({
          all: mailAccounts.map((a) => a.id),
          count: mailAccounts.length,
          results: (mailAccounts as PaperlessMailAccount[]).concat([]),
        })
      )
    }
    if (excludeService !== mailRuleService) {
      jest.spyOn(mailRuleService, 'listAll').mockReturnValue(
        of({
          all: mailRules.map((r) => r.id),
          count: mailRules.length,
          results: (mailRules as PaperlessMailRule[]).concat([]),
        })
      )
    }

    fixture = TestBed.createComponent(SettingsComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  }

  it('should support tabbed settings & change URL, prevent navigation if dirty confirmation rejected', () => {
    completeSetup()
    const navigateSpy = jest.spyOn(router, 'navigate')
    const tabButtons = fixture.debugElement.queryAll(By.directive(NgbNavLink))
    tabButtons[1].nativeElement.dispatchEvent(new MouseEvent('click'))
    expect(navigateSpy).toHaveBeenCalledWith(['settings', 'notifications'])
    tabButtons[2].nativeElement.dispatchEvent(new MouseEvent('click'))
    expect(navigateSpy).toHaveBeenCalledWith(['settings', 'savedviews'])
    tabButtons[3].nativeElement.dispatchEvent(new MouseEvent('click'))
    expect(navigateSpy).toHaveBeenCalledWith(['settings', 'mail'])
    tabButtons[4].nativeElement.dispatchEvent(new MouseEvent('click'))
    expect(navigateSpy).toHaveBeenCalledWith(['settings', 'usersgroups'])

    const initSpy = jest.spyOn(component, 'initialize')
    component.isDirty = true // mock dirty
    navigateSpy.mockResolvedValueOnce(false) // nav rejected cause dirty
    tabButtons[0].nativeElement.dispatchEvent(new MouseEvent('click'))
    expect(navigateSpy).toHaveBeenCalledWith(['settings', 'general'])
    expect(initSpy).not.toHaveBeenCalled()

    navigateSpy.mockResolvedValueOnce(true) // nav accepted even though dirty
    tabButtons[1].nativeElement.dispatchEvent(new MouseEvent('click'))
    expect(navigateSpy).toHaveBeenCalledWith(['settings', 'notifications'])
    expect(initSpy).toHaveBeenCalled()
  })

  it('should support direct link to tab by URL, scroll if needed', () => {
    completeSetup()
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap({ section: 'mail' })))
    activatedRoute.snapshot.fragment = '#mail'
    const scrollSpy = jest.spyOn(viewportScroller, 'scrollToAnchor')
    component.ngOnInit()
    expect(component.activeNavID).toEqual(4) // Mail
    component.ngAfterViewInit()
    expect(scrollSpy).toHaveBeenCalledWith('#mail')
  })

  it('should lazy load tab data', () => {
    completeSetup()
    const tabButtons = fixture.debugElement.queryAll(By.directive(NgbNavLink))

    expect(component.savedViews).toBeUndefined()
    tabButtons[2].nativeElement.dispatchEvent(
      new MouseEvent('mouseover', { bubbles: true })
    )
    expect(component.savedViews).not.toBeUndefined()

    expect(component.mailAccounts).toBeUndefined()
    tabButtons[3].nativeElement.dispatchEvent(
      new MouseEvent('mouseover', { bubbles: true })
    )
    expect(component.mailAccounts).not.toBeUndefined()

    expect(component.users).toBeUndefined()
    tabButtons[4].nativeElement.dispatchEvent(
      new MouseEvent('mouseover', { bubbles: true })
    )
    expect(component.users).not.toBeUndefined()
  })

  it('should support save saved views, show error', () => {
    completeSetup()
    component.maybeInitializeTab(3) // SavedViews

    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastSpy = jest.spyOn(toastService, 'show')
    const savedViewPatchSpy = jest.spyOn(savedViewService, 'patchMany')

    // saved views error first
    savedViewPatchSpy.mockReturnValueOnce(
      throwError(() => new Error('unable to save saved views'))
    )
    component.saveSettings()
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(savedViewPatchSpy).toHaveBeenCalled()
    toastSpy.mockClear()
    toastErrorSpy.mockClear()
    savedViewPatchSpy.mockClear()

    // succeed saved views
    savedViewPatchSpy.mockReturnValueOnce(
      of(savedViews as PaperlessSavedView[])
    )
    component.saveSettings()
    expect(toastErrorSpy).not.toHaveBeenCalled()
    expect(savedViewPatchSpy).toHaveBeenCalled()
  })

  it('should support save local settings updating appearance settings and calling API, show error', () => {
    completeSetup()
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastSpy = jest.spyOn(toastService, 'show')
    const storeSpy = jest.spyOn(settingsService, 'storeSettings')
    const appearanceSettingsSpy = jest.spyOn(
      settingsService,
      'updateAppearanceSettings'
    )
    const setSpy = jest.spyOn(settingsService, 'set')

    // error first
    storeSpy.mockReturnValueOnce(
      throwError(() => new Error('unable to save settings'))
    )
    component.saveSettings()
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(storeSpy).toHaveBeenCalled()
    expect(appearanceSettingsSpy).not.toHaveBeenCalled()
    expect(setSpy).toHaveBeenCalledTimes(19)

    // succeed
    storeSpy.mockReturnValueOnce(of(true))
    component.saveSettings()
    expect(toastSpy).toHaveBeenCalled()
    expect(appearanceSettingsSpy).toHaveBeenCalled()
  })

  it('should offer reload if settings changes require', () => {
    completeSetup()
    let toast: Toast
    toastService.getToasts().subscribe((t) => (toast = t[0]))
    component.initialize(true) // reset
    component.store.getValue()['displayLanguage'] = 'en-US'
    component.store.getValue()['updateCheckingEnabled'] = false
    component.settingsForm.value.displayLanguage = 'en-GB'
    component.settingsForm.value.updateCheckingEnabled = true
    jest.spyOn(settingsService, 'storeSettings').mockReturnValueOnce(of(true))
    component.saveSettings()
    expect(toast.actionName).toEqual('Reload now')
  })

  it('should allow setting theme color, visually apply change immediately but not save', () => {
    completeSetup()
    const appearanceSpy = jest.spyOn(
      settingsService,
      'updateAppearanceSettings'
    )
    const colorInput = fixture.debugElement.query(By.directive(ColorComponent))
    colorInput.query(By.css('input')).nativeElement.value = '#ff0000'
    colorInput
      .query(By.css('input'))
      .nativeElement.dispatchEvent(new Event('change'))
    fixture.detectChanges()
    expect(appearanceSpy).toHaveBeenCalled()
    expect(settingsService.get(SETTINGS_KEYS.THEME_COLOR)).toEqual('')
    component.clearThemeColor()
  })

  it('should support delete saved view', () => {
    completeSetup()
    component.maybeInitializeTab(3) // SavedViews
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    const deleteSpy = jest.spyOn(savedViewService, 'delete')
    deleteSpy.mockReturnValue(of(true))
    component.deleteSavedView(savedViews[0] as PaperlessSavedView)
    expect(deleteSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith(
      `Saved view "${savedViews[0].name}" deleted.`
    )
  })

  it('should support edit / create user, show error if needed', () => {
    completeSetup()
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((refs) => (modal = refs[0]))
    component.editUser(users[0])
    const editDialog = modal.componentInstance as UserEditDialogComponent
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    editDialog.failed.emit()
    expect(toastErrorSpy).toBeCalled()
    settingsService.currentUser = users[1] // simulate logged in as different user
    editDialog.succeeded.emit(users[0])
    expect(toastInfoSpy).toHaveBeenCalledWith(
      `Saved user "${users[0].username}".`
    )
  })

  it('should support delete user, show error if needed', () => {
    completeSetup()
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((refs) => (modal = refs[0]))
    component.deleteUser(users[0])
    const deleteDialog = modal.componentInstance as ConfirmDialogComponent
    const deleteSpy = jest.spyOn(userService, 'delete')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const listAllSpy = jest.spyOn(userService, 'listAll')
    deleteSpy.mockReturnValueOnce(
      throwError(() => new Error('error deleting user'))
    )
    deleteDialog.confirm()
    expect(toastErrorSpy).toBeCalled()
    deleteSpy.mockReturnValueOnce(of(true))
    deleteDialog.confirm()
    expect(listAllSpy).toHaveBeenCalled()
    expect(toastInfoSpy).toHaveBeenCalledWith('Deleted user')
  })

  it('should logout current user if password changed, after delay', fakeAsync(() => {
    completeSetup()
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((refs) => (modal = refs[0]))
    component.editUser(users[0])
    const editDialog = modal.componentInstance as UserEditDialogComponent
    editDialog.passwordIsSet = true
    settingsService.currentUser = users[0] // simulate logged in as same user
    editDialog.succeeded.emit(users[0])
    fixture.detectChanges()
    Object.defineProperty(window, 'location', {
      value: {
        href: 'http://localhost/',
      },
      writable: true, // possibility to override
    })
    tick(2600)
    expect(window.location.href).toContain('logout')
  }))

  it('should support edit / create group, show error if needed', () => {
    completeSetup()
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((refs) => (modal = refs[0]))
    component.editGroup(groups[0])
    const editDialog = modal.componentInstance as GroupEditDialogComponent
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    editDialog.failed.emit()
    expect(toastErrorSpy).toBeCalled()
    editDialog.succeeded.emit(groups[0])
    expect(toastInfoSpy).toHaveBeenCalledWith(
      `Saved group "${groups[0].name}".`
    )
  })

  it('should support delete group, show error if needed', () => {
    completeSetup()
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((refs) => (modal = refs[0]))
    component.deleteGroup(users[0])
    const deleteDialog = modal.componentInstance as ConfirmDialogComponent
    const deleteSpy = jest.spyOn(groupService, 'delete')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const listAllSpy = jest.spyOn(groupService, 'listAll')
    deleteSpy.mockReturnValueOnce(
      throwError(() => new Error('error deleting group'))
    )
    deleteDialog.confirm()
    expect(toastErrorSpy).toBeCalled()
    deleteSpy.mockReturnValueOnce(of(true))
    deleteDialog.confirm()
    expect(listAllSpy).toHaveBeenCalled()
    expect(toastInfoSpy).toHaveBeenCalledWith('Deleted group')
  })

  it('should get group name', () => {
    completeSetup()
    component.maybeInitializeTab(5) // UsersGroups
    expect(component.getGroupName(1)).toEqual(groups[0].name)
    expect(component.getGroupName(11)).toEqual('')
  })

  it('should show errors on load if load mailAccounts failure', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    jest
      .spyOn(mailAccountService, 'listAll')
      .mockImplementation(() =>
        throwError(() => new Error('failed to load mail accounts'))
      )
    completeSetup(mailAccountService)
    const tabButtons = fixture.debugElement.queryAll(By.directive(NgbNavLink))
    tabButtons[3].nativeElement.dispatchEvent(new MouseEvent('click')) // mail tab
    fixture.detectChanges()
    expect(toastErrorSpy).toBeCalled()
  })

  it('should show errors on load if load mailRules failure', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    jest
      .spyOn(mailRuleService, 'listAll')
      .mockImplementation(() =>
        throwError(() => new Error('failed to load mail rules'))
      )
    completeSetup(mailRuleService)
    const tabButtons = fixture.debugElement.queryAll(By.directive(NgbNavLink))
    tabButtons[3].nativeElement.dispatchEvent(new MouseEvent('click')) // mail tab
    fixture.detectChanges()
    // tabButtons[4].nativeElement.dispatchEvent(new MouseEvent('click'))
    expect(toastErrorSpy).toBeCalled()
  })

  it('should show errors on load if load users failure', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    jest
      .spyOn(userService, 'listAll')
      .mockImplementation(() =>
        throwError(() => new Error('failed to load users'))
      )
    completeSetup(userService)
    const tabButtons = fixture.debugElement.queryAll(By.directive(NgbNavLink))
    tabButtons[4].nativeElement.dispatchEvent(new MouseEvent('click')) // users tab
    fixture.detectChanges()
    expect(toastErrorSpy).toBeCalled()
  })

  it('should show errors on load if load groups failure', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    jest
      .spyOn(groupService, 'listAll')
      .mockImplementation(() =>
        throwError(() => new Error('failed to load groups'))
      )
    completeSetup(groupService)
    const tabButtons = fixture.debugElement.queryAll(By.directive(NgbNavLink))
    tabButtons[4].nativeElement.dispatchEvent(new MouseEvent('click')) // users tab
    fixture.detectChanges()
    expect(toastErrorSpy).toBeCalled()
  })

  it('should support edit / create mail account, show error if needed', () => {
    completeSetup()
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((refs) => (modal = refs[0]))
    component.editMailAccount(mailAccounts[0] as PaperlessMailAccount)
    const editDialog = modal.componentInstance as MailAccountEditDialogComponent
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    editDialog.failed.emit()
    expect(toastErrorSpy).toBeCalled()
    editDialog.succeeded.emit(mailAccounts[0])
    expect(toastInfoSpy).toHaveBeenCalledWith(
      `Saved account "${mailAccounts[0].name}".`
    )
  })

  it('should support delete mail account, show error if needed', () => {
    completeSetup()
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((refs) => (modal = refs[0]))
    component.deleteMailAccount(mailAccounts[0] as PaperlessMailAccount)
    const deleteDialog = modal.componentInstance as ConfirmDialogComponent
    const deleteSpy = jest.spyOn(mailAccountService, 'delete')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const listAllSpy = jest.spyOn(mailAccountService, 'listAll')
    deleteSpy.mockReturnValueOnce(
      throwError(() => new Error('error deleting mail account'))
    )
    deleteDialog.confirm()
    expect(toastErrorSpy).toBeCalled()
    deleteSpy.mockReturnValueOnce(of(true))
    deleteDialog.confirm()
    expect(listAllSpy).toHaveBeenCalled()
    expect(toastInfoSpy).toHaveBeenCalledWith('Deleted mail account')
  })

  it('should support edit / create mail rule, show error if needed', () => {
    completeSetup()
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((refs) => (modal = refs[0]))
    component.editMailRule(mailRules[0] as PaperlessMailRule)
    const editDialog = modal.componentInstance as MailRuleEditDialogComponent
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    editDialog.failed.emit()
    expect(toastErrorSpy).toBeCalled()
    editDialog.succeeded.emit(mailRules[0])
    expect(toastInfoSpy).toHaveBeenCalledWith(
      `Saved rule "${mailRules[0].name}".`
    )
  })

  it('should support delete mail rule, show error if needed', () => {
    completeSetup()
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((refs) => (modal = refs[0]))
    component.deleteMailRule(mailRules[0] as PaperlessMailRule)
    const deleteDialog = modal.componentInstance as ConfirmDialogComponent
    const deleteSpy = jest.spyOn(mailRuleService, 'delete')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const listAllSpy = jest.spyOn(mailRuleService, 'listAll')
    deleteSpy.mockReturnValueOnce(
      throwError(() => new Error('error deleting mail rule'))
    )
    deleteDialog.confirm()
    expect(toastErrorSpy).toBeCalled()
    deleteSpy.mockReturnValueOnce(of(true))
    deleteDialog.confirm()
    expect(listAllSpy).toHaveBeenCalled()
    expect(toastInfoSpy).toHaveBeenCalledWith('Deleted mail rule')
  })
})
