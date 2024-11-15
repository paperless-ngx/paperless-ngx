import { ViewportScroller, DatePipe } from '@angular/common'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { Router, ActivatedRoute, convertToParamMap } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import {
  NgbModule,
  NgbAlertModule,
  NgbNavLink,
  NgbModal,
  NgbModalModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { of, throwError } from 'rxjs'
import { routes } from 'src/app/app-routing.module'
import { SavedView } from 'src/app/data/saved-view'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { PermissionsService } from 'src/app/services/permissions.service'
import { GroupService } from 'src/app/services/rest/group.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService, Toast } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { CheckComponent } from '../../common/input/check/check.component'
import { ColorComponent } from '../../common/input/color/color.component'
import { NumberComponent } from '../../common/input/number/number.component'
import { PermissionsGroupComponent } from '../../common/input/permissions/permissions-group/permissions-group.component'
import { PermissionsUserComponent } from '../../common/input/permissions/permissions-user/permissions-user.component'
import { SelectComponent } from '../../common/input/select/select.component'
import { TagsComponent } from '../../common/input/tags/tags.component'
import { TextComponent } from '../../common/input/text/text.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { SettingsComponent } from './settings.component'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { ConfirmButtonComponent } from '../../common/confirm-button/confirm-button.component'
import { SystemStatusDialogComponent } from '../../common/system-status-dialog/system-status-dialog.component'
import { SystemStatusService } from 'src/app/services/system-status.service'
import {
  SystemStatus,
  InstallType,
  SystemStatusItemStatus,
} from 'src/app/data/system-status'
import { DragDropSelectComponent } from '../../common/input/drag-drop-select/drag-drop-select.component'
import { DragDropModule } from '@angular/cdk/drag-drop'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

const savedViews = [
  { id: 1, name: 'view1', show_in_sidebar: true, show_on_dashboard: true },
  { id: 2, name: 'view2', show_in_sidebar: false, show_on_dashboard: false },
]
const users = [
  { id: 1, username: 'user1', is_superuser: false },
  { id: 2, username: 'user2', is_superuser: false },
]
const groups = [
  { id: 1, name: 'group1' },
  { id: 2, name: 'group2' },
]

describe('SettingsComponent', () => {
  let component: SettingsComponent
  let fixture: ComponentFixture<SettingsComponent>
  let router: Router
  let settingsService: SettingsService
  let savedViewService: SavedViewService
  let activatedRoute: ActivatedRoute
  let viewportScroller: ViewportScroller
  let toastService: ToastService
  let userService: UserService
  let permissionsService: PermissionsService
  let groupService: GroupService
  let modalService: NgbModal
  let systemStatusService: SystemStatusService

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
        NumberComponent,
        TagsComponent,
        PermissionsUserComponent,
        PermissionsGroupComponent,
        IfOwnerDirective,
        ConfirmButtonComponent,
        DragDropSelectComponent,
      ],
      imports: [
        NgbModule,
        RouterTestingModule.withRoutes(routes),
        FormsModule,
        ReactiveFormsModule,
        NgbAlertModule,
        NgSelectModule,
        NgxBootstrapIconsModule.pick(allIcons),
        NgbModalModule,
        DragDropModule,
      ],
      providers: [
        CustomDatePipe,
        DatePipe,
        PermissionsGuard,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    router = TestBed.inject(Router)
    activatedRoute = TestBed.inject(ActivatedRoute)
    viewportScroller = TestBed.inject(ViewportScroller)
    toastService = TestBed.inject(ToastService)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = users[0]
    userService = TestBed.inject(UserService)
    permissionsService = TestBed.inject(PermissionsService)
    modalService = TestBed.inject(NgbModal)
    systemStatusService = TestBed.inject(SystemStatusService)
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    jest
      .spyOn(permissionsService, 'currentUserOwnsObject')
      .mockReturnValue(true)
    groupService = TestBed.inject(GroupService)
    savedViewService = TestBed.inject(SavedViewService)
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
          results: (savedViews as SavedView[]).concat([]),
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
    expect(navigateSpy).toHaveBeenCalledWith(['settings', 'permissions'])
    tabButtons[2].nativeElement.dispatchEvent(new MouseEvent('click'))
    expect(navigateSpy).toHaveBeenCalledWith(['settings', 'notifications'])
    tabButtons[3].nativeElement.dispatchEvent(new MouseEvent('click'))
    expect(navigateSpy).toHaveBeenCalledWith(['settings', 'savedviews'])

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
      .mockReturnValue(of(convertToParamMap({ section: 'notifications' })))
    activatedRoute.snapshot.fragment = '#notifications'
    const scrollSpy = jest.spyOn(viewportScroller, 'scrollToAnchor')
    component.ngOnInit()
    expect(component.activeNavID).toEqual(3) // Notifications
    component.ngAfterViewInit()
    expect(scrollSpy).toHaveBeenCalledWith('#notifications')
  })

  it('should enable organizing of sidebar saved views even on direct navigation', () => {
    completeSetup()
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap({ section: 'savedviews' })))
    activatedRoute.snapshot.fragment = '#savedviews'
    component.ngOnInit()
    expect(component.activeNavID).toEqual(4) // Saved Views
    component.ngAfterViewInit()
    expect(settingsService.organizingSidebarSavedViews).toBeTruthy()
  })

  it('should support save saved views, show error', () => {
    completeSetup()

    const tabButtons = fixture.debugElement.queryAll(By.directive(NgbNavLink))
    tabButtons[3].nativeElement.dispatchEvent(new MouseEvent('click'))
    fixture.detectChanges()

    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastSpy = jest.spyOn(toastService, 'show')
    const savedViewPatchSpy = jest.spyOn(savedViewService, 'patchMany')

    const toggle = fixture.debugElement.query(
      By.css('.form-check.form-switch input')
    )
    toggle.nativeElement.checked = true
    toggle.nativeElement.dispatchEvent(new Event('change'))

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
    savedViewPatchSpy.mockReturnValueOnce(of(savedViews as SavedView[]))
    component.saveSettings()
    expect(toastErrorSpy).not.toHaveBeenCalled()
    expect(savedViewPatchSpy).toHaveBeenCalled()
  })

  it('should update only patch saved views that have changed', () => {
    completeSetup()

    const tabButtons = fixture.debugElement.queryAll(By.directive(NgbNavLink))
    tabButtons[3].nativeElement.dispatchEvent(new MouseEvent('click'))
    fixture.detectChanges()

    const patchSpy = jest.spyOn(savedViewService, 'patchMany')
    component.saveSettings()
    expect(patchSpy).not.toHaveBeenCalled()

    const view = savedViews[0]
    const toggle = fixture.debugElement.query(
      By.css('.form-check.form-switch input')
    )
    toggle.nativeElement.checked = true
    toggle.nativeElement.dispatchEvent(new Event('change'))
    // register change
    component.savedViewGroup.get(view.id.toString()).value[
      'show_on_dashboard'
    ] = !view.show_on_dashboard
    fixture.detectChanges()

    component.saveSettings()
    expect(patchSpy).toHaveBeenCalledWith([
      {
        id: view.id,
        name: view.name,
        show_in_sidebar: view.show_in_sidebar,
        show_on_dashboard: !view.show_on_dashboard,
      },
    ])
  })

  it('should support save local settings updating appearance settings and calling API, show error', () => {
    completeSetup()
    jest.spyOn(savedViewService, 'patchMany').mockReturnValue(of([]))
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
    expect(setSpy).toHaveBeenCalledTimes(28)

    // succeed
    storeSpy.mockReturnValueOnce(of(true))
    component.saveSettings()
    expect(toastSpy).toHaveBeenCalled()
    expect(appearanceSettingsSpy).toHaveBeenCalled()
  })

  it('should offer reload if settings changes require', () => {
    completeSetup()
    jest.spyOn(savedViewService, 'patchMany').mockReturnValue(of([]))
    let toast: Toast
    toastService.getToasts().subscribe((t) => (toast = t[0]))
    component.initialize(true) // reset
    component.store.getValue()['displayLanguage'] = 'en-US'
    component.store.getValue()['updateCheckingEnabled'] = false
    component.settingsForm.value.displayLanguage = 'en-GB'
    jest.spyOn(settingsService, 'storeSettings').mockReturnValue(of(true))
    component.saveSettings()
    expect(toast.actionName).toEqual('Reload now')

    component.settingsForm.value.updateCheckingEnabled = true
    component.saveSettings()

    expect(toast.actionName).toEqual('Reload now')
    toast.action()
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
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    const deleteSpy = jest.spyOn(savedViewService, 'delete')
    deleteSpy.mockReturnValue(of(true))
    component.deleteSavedView(savedViews[0] as SavedView)
    expect(deleteSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith(
      `Saved view "${savedViews[0].name}" deleted.`
    )
  })

  it('should show errors on load if load users failure', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    jest
      .spyOn(userService, 'listAll')
      .mockImplementation(() =>
        throwError(() => new Error('failed to load users'))
      )
    completeSetup(userService)
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
    fixture.detectChanges()
    expect(toastErrorSpy).toBeCalled()
  })

  it('should load system status on initialize, show errors if needed', () => {
    const status: SystemStatus = {
      pngx_version: '2.4.3',
      server_os: 'macOS-14.1.1-arm64-arm-64bit',
      install_type: InstallType.BareMetal,
      storage: { total: 494384795648, available: 13573525504 },
      database: {
        type: 'sqlite',
        url: '/paperless-ngx/data/db.sqlite3',
        status: SystemStatusItemStatus.ERROR,
        error: null,
        migration_status: {
          latest_migration: 'socialaccount.0006_alter_socialaccount_extra_data',
          unapplied_migrations: [],
        },
      },
      tasks: {
        redis_url: 'redis://localhost:6379',
        redis_status: SystemStatusItemStatus.ERROR,
        redis_error:
          'Error 61 connecting to localhost:6379. Connection refused.',
        celery_status: SystemStatusItemStatus.ERROR,
        index_status: SystemStatusItemStatus.OK,
        index_last_modified: new Date().toISOString(),
        index_error: null,
        classifier_status: SystemStatusItemStatus.OK,
        classifier_last_trained: new Date().toISOString(),
        classifier_error: null,
      },
    }
    jest.spyOn(systemStatusService, 'get').mockReturnValue(of(status))
    jest.spyOn(permissionsService, 'isAdmin').mockReturnValue(true)
    completeSetup()
    expect(component['systemStatus']).toEqual(status) // private
    expect(component.systemStatusHasErrors).toBeTruthy()
    // coverage
    component['systemStatus'].database.status = SystemStatusItemStatus.OK
    component['systemStatus'].tasks.redis_status = SystemStatusItemStatus.OK
    component['systemStatus'].tasks.celery_status = SystemStatusItemStatus.OK
    expect(component.systemStatusHasErrors).toBeFalsy()
  })

  it('should open system status dialog', () => {
    const modalOpenSpy = jest.spyOn(modalService, 'open')
    completeSetup()
    component.showSystemStatus()
    expect(modalOpenSpy).toHaveBeenCalledWith(SystemStatusDialogComponent, {
      size: 'xl',
    })
  })

  it('should support reset', () => {
    completeSetup()
    component.settingsForm.get('themeColor').setValue('#ff0000')
    component.reset()
    expect(component.settingsForm.get('themeColor').value).toEqual('')
  })
})
