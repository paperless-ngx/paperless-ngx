import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  fakeAsync,
  TestBed,
  tick,
} from '@angular/core/testing'
import { Router, RouterModule } from '@angular/router'
import { NgbModalModule } from '@ng-bootstrap/ng-bootstrap'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { NgxFileDropModule } from 'ngx-file-drop'
import { TourNgBootstrapModule, TourService } from 'ngx-ui-tour-ng-bootstrap'
import { Subject } from 'rxjs'
import { routes } from './app-routing.module'
import { AppComponent } from './app.component'
import { NotificationListComponent } from './components/common/notification-list/notification-list.component'
import { FileDropComponent } from './components/file-drop/file-drop.component'
import { DirtySavedViewGuard } from './guards/dirty-saved-view.guard'
import { PermissionsGuard } from './guards/permissions.guard'
import { HotKeyService } from './services/hot-key.service'
import {
  Notification,
  NotificationService,
} from './services/notification.service'
import { PermissionsService } from './services/permissions.service'
import { SettingsService } from './services/settings.service'
import {
  FileStatus,
  WebsocketStatusService,
} from './services/websocket-status.service'

describe('AppComponent', () => {
  let component: AppComponent
  let fixture: ComponentFixture<AppComponent>
  let tourService: TourService
  let websocketStatusService: WebsocketStatusService
  let permissionsService: PermissionsService
  let notificationService: NotificationService
  let router: Router
  let settingsService: SettingsService
  let hotKeyService: HotKeyService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        TourNgBootstrapModule,
        RouterModule.forRoot(routes),
        NgxFileDropModule,
        NgbModalModule,
        AppComponent,
        NotificationListComponent,
        FileDropComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        PermissionsGuard,
        DirtySavedViewGuard,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    tourService = TestBed.inject(TourService)
    websocketStatusService = TestBed.inject(WebsocketStatusService)
    permissionsService = TestBed.inject(PermissionsService)
    settingsService = TestBed.inject(SettingsService)
    notificationService = TestBed.inject(NotificationService)
    router = TestBed.inject(Router)
    hotKeyService = TestBed.inject(HotKeyService)
    fixture = TestBed.createComponent(AppComponent)
    component = fixture.componentInstance
  })

  it('should initialize the tour service & toggle class on body for styling', fakeAsync(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => {})
    fixture.detectChanges()
    const tourSpy = jest.spyOn(tourService, 'initialize')
    component.ngOnInit()
    expect(tourSpy).toHaveBeenCalled()
    tourService.start()
    expect(document.body.classList).toContain('tour-active')
    tourService.end()
    tick(500)
    expect(document.body.classList).not.toContain('tour-active')
  }))

  it('should display notification on document consumed with link if user has access', () => {
    const navigateSpy = jest.spyOn(router, 'navigate')
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    let notification: Notification
    notificationService
      .getNotifications()
      .subscribe((notifications) => (notification = notifications[0]))
    const notificationSpy = jest.spyOn(notificationService, 'show')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(websocketStatusService, 'onDocumentConsumptionFinished')
      .mockReturnValue(fileStatusSubject)
    component.ngOnInit()
    const status = new FileStatus()
    status.documentId = 1
    fileStatusSubject.next(status)
    expect(notificationSpy).toHaveBeenCalled()
    expect(notification.action).not.toBeUndefined()
    notification.action()
    expect(navigateSpy).toHaveBeenCalledWith(['documents', status.documentId])
  })

  it('should display notification on document consumed without link if user does not have access', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(false)
    let notification: Notification
    notificationService
      .getNotifications()
      .subscribe((notifications) => (notification = notifications[0]))
    const notificationSpy = jest.spyOn(notificationService, 'show')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(websocketStatusService, 'onDocumentConsumptionFinished')
      .mockReturnValue(fileStatusSubject)
    component.ngOnInit()
    fileStatusSubject.next(new FileStatus())
    expect(notificationSpy).toHaveBeenCalled()
    expect(notification.action).toBeUndefined()
  })

  it('should display notification on document added', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    const notificationSpy = jest.spyOn(notificationService, 'show')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(websocketStatusService, 'onDocumentDetected')
      .mockReturnValue(fileStatusSubject)
    component.ngOnInit()
    fileStatusSubject.next(new FileStatus())
    expect(notificationSpy).toHaveBeenCalled()
  })

  it('should suppress dashboard notifications if set', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest.spyOn(settingsService, 'get').mockReturnValue(true)
    jest.spyOn(router, 'url', 'get').mockReturnValue('/dashboard')
    const notificationSpy = jest.spyOn(notificationService, 'show')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(websocketStatusService, 'onDocumentDetected')
      .mockReturnValue(fileStatusSubject)
    component.ngOnInit()
    fileStatusSubject.next(new FileStatus())
    expect(notificationSpy).not.toHaveBeenCalled()
  })

  it('should display notification on document failed', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    const notificationSpy = jest.spyOn(notificationService, 'showError')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(websocketStatusService, 'onDocumentConsumptionFailed')
      .mockReturnValue(fileStatusSubject)
    component.ngOnInit()
    fileStatusSubject.next(new FileStatus())
    expect(notificationSpy).toHaveBeenCalled()
  })

  it('should support hotkeys', () => {
    const addShortcutSpy = jest.spyOn(hotKeyService, 'addShortcut')
    const routerSpy = jest.spyOn(router, 'navigate')
    // prevent actual navigation
    routerSpy.mockReturnValue(new Promise(() => {}))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    component.ngOnInit()
    expect(addShortcutSpy).toHaveBeenCalled()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'h' }))
    expect(routerSpy).toHaveBeenCalledWith(['/dashboard'])
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'd' }))
    expect(routerSpy).toHaveBeenCalledWith(['/documents'])
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 's' }))
    expect(routerSpy).toHaveBeenCalledWith(['/settings'])
  })
})
