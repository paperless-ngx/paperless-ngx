import { HttpClientTestingModule } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { Router } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import { TourService, TourNgBootstrapModule } from 'ngx-ui-tour-ng-bootstrap'
import { Subject } from 'rxjs'
import { routes } from './app-routing.module'
import { AppComponent } from './app.component'
import { ToastsComponent } from './components/common/toasts/toasts.component'
import {
  ConsumerStatusService,
  FileStatus,
} from './services/consumer-status.service'
import { PermissionsService } from './services/permissions.service'
import { ToastService, Toast } from './services/toast.service'
import { SettingsService } from './services/settings.service'
import { FileDropComponent } from './components/file-drop/file-drop.component'
import { NgxFileDropModule } from 'ngx-file-drop'

describe('AppComponent', () => {
  let component: AppComponent
  let fixture: ComponentFixture<AppComponent>
  let tourService: TourService
  let consumerStatusService: ConsumerStatusService
  let permissionsService: PermissionsService
  let toastService: ToastService
  let router: Router
  let settingsService: SettingsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [AppComponent, ToastsComponent, FileDropComponent],
      providers: [],
      imports: [
        HttpClientTestingModule,
        TourNgBootstrapModule,
        RouterTestingModule.withRoutes(routes),
        NgxFileDropModule,
      ],
    }).compileComponents()

    tourService = TestBed.inject(TourService)
    consumerStatusService = TestBed.inject(ConsumerStatusService)
    permissionsService = TestBed.inject(PermissionsService)
    settingsService = TestBed.inject(SettingsService)
    toastService = TestBed.inject(ToastService)
    router = TestBed.inject(Router)
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

  it('should display toast on document consumed with link if user has access', () => {
    const navigateSpy = jest.spyOn(router, 'navigate')
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    let toast: Toast
    toastService.getToasts().subscribe((toasts) => (toast = toasts[0]))
    const toastSpy = jest.spyOn(toastService, 'show')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(consumerStatusService, 'onDocumentConsumptionFinished')
      .mockReturnValue(fileStatusSubject)
    component.ngOnInit()
    const status = new FileStatus()
    status.documentId = 1
    fileStatusSubject.next(status)
    expect(toastSpy).toHaveBeenCalled()
    expect(toast.action).not.toBeUndefined()
    toast.action()
    expect(navigateSpy).toHaveBeenCalledWith(['documents', status.documentId])
  })

  it('should display toast on document consumed without link if user does not have access', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(false)
    let toast: Toast
    toastService.getToasts().subscribe((toasts) => (toast = toasts[0]))
    const toastSpy = jest.spyOn(toastService, 'show')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(consumerStatusService, 'onDocumentConsumptionFinished')
      .mockReturnValue(fileStatusSubject)
    component.ngOnInit()
    fileStatusSubject.next(new FileStatus())
    expect(toastSpy).toHaveBeenCalled()
    expect(toast.action).toBeUndefined()
  })

  it('should display toast on document added', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    const toastSpy = jest.spyOn(toastService, 'show')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(consumerStatusService, 'onDocumentDetected')
      .mockReturnValue(fileStatusSubject)
    component.ngOnInit()
    fileStatusSubject.next(new FileStatus())
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should suppress dashboard notifications if set', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest.spyOn(settingsService, 'get').mockReturnValue(true)
    jest.spyOn(router, 'url', 'get').mockReturnValue('/dashboard')
    const toastSpy = jest.spyOn(toastService, 'show')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(consumerStatusService, 'onDocumentDetected')
      .mockReturnValue(fileStatusSubject)
    component.ngOnInit()
    fileStatusSubject.next(new FileStatus())
    expect(toastSpy).not.toHaveBeenCalled()
  })

  it('should display toast on document failed', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    const toastSpy = jest.spyOn(toastService, 'showError')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(consumerStatusService, 'onDocumentConsumptionFailed')
      .mockReturnValue(fileStatusSubject)
    component.ngOnInit()
    fileStatusSubject.next(new FileStatus())
    expect(toastSpy).toHaveBeenCalled()
  })
})
