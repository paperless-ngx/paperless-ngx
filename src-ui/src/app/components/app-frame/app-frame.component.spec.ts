import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { AppFrameComponent } from './app-frame.component'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { NgbModal, NgbModalModule, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { BrowserModule } from '@angular/platform-browser'
import { RouterTestingModule } from '@angular/router/testing'
import { SettingsService } from 'src/app/services/settings.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { RemoteVersionService } from 'src/app/services/rest/remote-version.service'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { of, throwError } from 'rxjs'
import { ToastService } from 'src/app/services/toast.service'
import {
  DjangoMessageLevel,
  DjangoMessagesService,
} from 'src/app/services/django-messages.service'
import { environment } from 'src/environments/environment'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { ActivatedRoute, Router } from '@angular/router'
import { DocumentDetailComponent } from '../document-detail/document-detail.component'
import { SearchService } from 'src/app/services/rest/search.service'
import { routes } from 'src/app/app-routing.module'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { CdkDragDrop, DragDropModule } from '@angular/cdk/drag-drop'
import { SavedView } from 'src/app/data/saved-view'
import { ProfileEditDialogComponent } from '../common/profile-edit-dialog/profile-edit-dialog.component'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { GlobalSearchComponent } from './global-search/global-search.component'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

const saved_views = [
  {
    name: 'Saved View 0',
    id: 0,
    show_on_dashboard: true,
    show_in_sidebar: true,
    sort_field: 'name',
    sort_reverse: true,
    filter_rules: [],
  },
  {
    name: 'Saved View 1',
    id: 1,
    show_on_dashboard: false,
    show_in_sidebar: false,
    sort_field: 'name',
    sort_reverse: true,
    filter_rules: [],
  },
  {
    name: 'Saved View 2',
    id: 2,
    show_on_dashboard: true,
    show_in_sidebar: true,
    sort_field: 'name',
    sort_reverse: true,
    filter_rules: [],
  },
  {
    name: 'Saved View 3',
    id: 3,
    show_on_dashboard: true,
    show_in_sidebar: true,
    sort_field: 'name',
    sort_reverse: true,
    filter_rules: [],
  },
]
const document = { id: 2, title: 'Hello world' }

describe('AppFrameComponent', () => {
  let component: AppFrameComponent
  let fixture: ComponentFixture<AppFrameComponent>
  let httpTestingController: HttpTestingController
  let settingsService: SettingsService
  let permissionsService: PermissionsService
  let remoteVersionService: RemoteVersionService
  let toastService: ToastService
  let messagesService: DjangoMessagesService
  let openDocumentsService: OpenDocumentsService
  let router: Router
  let savedViewSpy
  let modalService: NgbModal

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        AppFrameComponent,
        IfPermissionsDirective,
        GlobalSearchComponent,
      ],
      imports: [
        BrowserModule,
        RouterTestingModule.withRoutes(routes),
        NgbModule,
        FormsModule,
        ReactiveFormsModule,
        DragDropModule,
        NgbModalModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        SettingsService,
        {
          provide: SavedViewService,
          useValue: {
            reload: () => {},
            listAll: () =>
              of({
                all: [saved_views.map((v) => v.id)],
                count: saved_views.length,
                results: saved_views,
              }),
            sidebarViews: saved_views.filter((v) => v.show_in_sidebar),
          },
        },
        PermissionsService,
        RemoteVersionService,
        IfPermissionsDirective,
        ToastService,
        DjangoMessagesService,
        OpenDocumentsService,
        SearchService,
        NgbModal,
        {
          provide: ActivatedRoute,
          useValue: {
            firstChild: {
              component: DocumentDetailComponent,
            },
            snapshot: {
              firstChild: {
                component: DocumentDetailComponent,
                params: {
                  id: document.id,
                },
              },
            },
          },
        },
        PermissionsGuard,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    settingsService = TestBed.inject(SettingsService)
    const savedViewService = TestBed.inject(SavedViewService)
    permissionsService = TestBed.inject(PermissionsService)
    remoteVersionService = TestBed.inject(RemoteVersionService)
    toastService = TestBed.inject(ToastService)
    messagesService = TestBed.inject(DjangoMessagesService)
    openDocumentsService = TestBed.inject(OpenDocumentsService)
    modalService = TestBed.inject(NgbModal)
    router = TestBed.inject(Router)

    jest
      .spyOn(settingsService, 'displayName', 'get')
      .mockReturnValue('Hello World')
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)

    savedViewSpy = jest.spyOn(savedViewService, 'reload')

    fixture = TestBed.createComponent(AppFrameComponent)
    component = fixture.componentInstance

    httpTestingController = TestBed.inject(HttpTestingController)

    fixture.detectChanges()
  })

  it('should initialize the saved view service', () => {
    expect(savedViewSpy).toHaveBeenCalled()
  })

  it('should check for update if enabled', () => {
    const updateCheckSpy = jest.spyOn(remoteVersionService, 'checkForUpdates')
    updateCheckSpy.mockImplementation(() => {
      return of({
        version: 'v100.0',
        update_available: true,
      })
    })
    settingsService.set(SETTINGS_KEYS.UPDATE_CHECKING_ENABLED, true)
    component.ngOnInit()
    expect(updateCheckSpy).toHaveBeenCalled()
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain('Update available')
  })

  it('should check not for update if disabled', () => {
    const updateCheckSpy = jest.spyOn(remoteVersionService, 'checkForUpdates')
    settingsService.set(SETTINGS_KEYS.UPDATE_CHECKING_ENABLED, false)
    component.ngOnInit()
    fixture.detectChanges()
    expect(updateCheckSpy).not.toHaveBeenCalled()
    expect(fixture.nativeElement.textContent).not.toContain('Update available')
  })

  it('should check for update if was disabled and then enabled', () => {
    const updateCheckSpy = jest.spyOn(remoteVersionService, 'checkForUpdates')
    settingsService.set(SETTINGS_KEYS.UPDATE_CHECKING_ENABLED, false)
    component.setUpdateChecking(true)
    fixture.detectChanges()
    expect(updateCheckSpy).toHaveBeenCalled()
  })

  it('should show error on toggle update checking if store settings fails', () => {
    jest.spyOn(console, 'warn').mockImplementation(() => {})
    const toastSpy = jest.spyOn(toastService, 'showError')
    settingsService.set(SETTINGS_KEYS.UPDATE_CHECKING_ENABLED, false)
    component.setUpdateChecking(true)
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}ui_settings/`)
      .flush('error', {
        status: 500,
        statusText: 'error',
      })
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should support toggling slim sidebar and saving', fakeAsync(() => {
    const saveSettingSpy = jest.spyOn(settingsService, 'set')
    expect(component.slimSidebarEnabled).toBeFalsy()
    expect(component.slimSidebarAnimating).toBeFalsy()
    component.toggleSlimSidebar()
    expect(component.slimSidebarAnimating).toBeTruthy()
    tick(200)
    expect(component.slimSidebarAnimating).toBeFalsy()
    expect(component.slimSidebarEnabled).toBeTruthy()
    expect(saveSettingSpy).toHaveBeenCalledWith(
      SETTINGS_KEYS.SLIM_SIDEBAR,
      true
    )
  }))

  it('should show error on toggle slim sidebar if store settings fails', () => {
    jest.spyOn(console, 'warn').mockImplementation(() => {})
    const toastSpy = jest.spyOn(toastService, 'showError')
    component.toggleSlimSidebar()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}ui_settings/`)
      .flush('error', {
        status: 500,
        statusText: 'error',
      })
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should support collapsible menu', () => {
    const button: HTMLButtonElement = (
      fixture.nativeElement as HTMLDivElement
    ).querySelector('button[data-toggle=collapse]')
    button.dispatchEvent(new MouseEvent('click'))
    expect(component.isMenuCollapsed).toBeFalsy()
    component.closeMenu()
    expect(component.isMenuCollapsed).toBeTruthy()
  })

  it('should support close document & navigate on close current doc', () => {
    const closeSpy = jest.spyOn(openDocumentsService, 'closeDocument')
    closeSpy.mockReturnValue(of(true))
    const routerSpy = jest.spyOn(router, 'navigate')
    component.closeDocument(document)
    expect(closeSpy).toHaveBeenCalledWith(document)
    expect(routerSpy).toHaveBeenCalled()
  })

  it('should support close all documents & navigate on close current doc', () => {
    const closeAllSpy = jest.spyOn(openDocumentsService, 'closeAll')
    closeAllSpy.mockReturnValue(of(true))
    const routerSpy = jest.spyOn(router, 'navigate')
    component.closeAll()
    expect(closeAllSpy).toHaveBeenCalled()
    expect(routerSpy).toHaveBeenCalled()
  })

  it('should close all documents on logout', () => {
    const closeAllSpy = jest.spyOn(openDocumentsService, 'closeAll')
    component.onLogout()
    expect(closeAllSpy).toHaveBeenCalled()
  })

  it('should warn before close if dirty documents', () => {
    jest.spyOn(openDocumentsService, 'hasDirty').mockReturnValue(true)
    expect(component.canDeactivate()).toBeFalsy()
  })

  it('should disable global dropzone on start drag + drop, re-enable after', () => {
    expect(settingsService.globalDropzoneEnabled).toBeTruthy()
    component.onDragStart(null)
    expect(settingsService.globalDropzoneEnabled).toBeFalsy()
    component.onDragEnd(null)
    expect(settingsService.globalDropzoneEnabled).toBeTruthy()
  })

  it('should update saved view sorting on drag + drop, show info', () => {
    const settingsSpy = jest.spyOn(settingsService, 'updateSidebarViewsSort')
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    jest.spyOn(settingsService, 'storeSettings').mockReturnValue(of(true))
    component.onDrop({ previousIndex: 0, currentIndex: 1 } as CdkDragDrop<
      SavedView[]
    >)
    expect(settingsSpy).toHaveBeenCalledWith([
      saved_views[2],
      saved_views[0],
      saved_views[3],
    ])
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should update saved view sorting on drag + drop, show error', () => {
    jest.spyOn(settingsService, 'get').mockImplementation((key) => {
      if (key === SETTINGS_KEYS.SIDEBAR_VIEWS_SORT_ORDER) return []
    })
    fixture.destroy()
    fixture = TestBed.createComponent(AppFrameComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
    const toastSpy = jest.spyOn(toastService, 'showError')
    jest
      .spyOn(settingsService, 'storeSettings')
      .mockReturnValue(throwError(() => new Error('unable to save')))
    component.onDrop({ previousIndex: 0, currentIndex: 2 } as CdkDragDrop<
      SavedView[]
    >)
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should support edit profile', () => {
    const modalSpy = jest.spyOn(modalService, 'open')
    component.editProfile()
    expect(modalSpy).toHaveBeenCalledWith(ProfileEditDialogComponent, {
      backdrop: 'static',
      size: 'xl',
    })
  })

  it('should show toasts for django messages', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    jest.spyOn(messagesService, 'get').mockReturnValue([
      { level: DjangoMessageLevel.WARNING, message: 'Test warning' },
      { level: DjangoMessageLevel.ERROR, message: 'Test error' },
      { level: DjangoMessageLevel.SUCCESS, message: 'Test success' },
      { level: DjangoMessageLevel.INFO, message: 'Test info' },
      { level: DjangoMessageLevel.DEBUG, message: 'Test debug' },
    ])
    component.ngOnInit()
    expect(toastErrorSpy).toHaveBeenCalledTimes(2)
    expect(toastInfoSpy).toHaveBeenCalledTimes(3)
  })
})
