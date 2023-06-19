import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { AppFrameComponent } from './app-frame.component'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { BrowserModule } from '@angular/platform-browser'
import { RouterTestingModule } from '@angular/router/testing'
import { SettingsService } from 'src/app/services/settings.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { SETTINGS_KEYS } from 'src/app/data/paperless-uisettings'
import { RemoteVersionService } from 'src/app/services/rest/remote-version.service'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { of } from 'rxjs'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { ActivatedRoute, Router } from '@angular/router'
import { DocumentDetailComponent } from '../document-detail/document-detail.component'
import { SearchService } from 'src/app/services/rest/search.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_FULLTEXT_QUERY } from 'src/app/data/filter-rule-type'
import { routes } from 'src/app/app-routing.module'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'

const document = { id: 2, title: 'Hello world' }

describe('AppFrameComponent', () => {
  let component: AppFrameComponent
  let fixture: ComponentFixture<AppFrameComponent>
  let httpTestingController: HttpTestingController
  let settingsService: SettingsService
  let permissionsService: PermissionsService
  let remoteVersionService: RemoteVersionService
  let toastService: ToastService
  let openDocumentsService: OpenDocumentsService
  let searchService: SearchService
  let documentListViewService: DocumentListViewService
  let router: Router
  let savedViewSpy

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [AppFrameComponent, IfPermissionsDirective],
      imports: [
        HttpClientTestingModule,
        BrowserModule,
        RouterTestingModule.withRoutes(routes),
        NgbModule,
        FormsModule,
        ReactiveFormsModule,
      ],
      providers: [
        SettingsService,
        SavedViewService,
        PermissionsService,
        RemoteVersionService,
        IfPermissionsDirective,
        ToastService,
        OpenDocumentsService,
        SearchService,
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
      ],
    }).compileComponents()

    settingsService = TestBed.inject(SettingsService)
    const savedViewService = TestBed.inject(SavedViewService)
    permissionsService = TestBed.inject(PermissionsService)
    remoteVersionService = TestBed.inject(RemoteVersionService)
    toastService = TestBed.inject(ToastService)
    openDocumentsService = TestBed.inject(OpenDocumentsService)
    searchService = TestBed.inject(SearchService)
    documentListViewService = TestBed.inject(DocumentListViewService)
    router = TestBed.inject(Router)

    jest
      .spyOn(settingsService, 'displayName', 'get')
      .mockReturnValue('Hello World')
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)

    savedViewSpy = jest.spyOn(savedViewService, 'initialize')

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

  it('should support collapsable menu', () => {
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

  it('should call autocomplete endpoint on input', fakeAsync(() => {
    const autocompleteSpy = jest.spyOn(searchService, 'autocomplete')
    component.searchAutoComplete(of('hello')).subscribe()
    tick(250)
    expect(autocompleteSpy).toHaveBeenCalled()

    component.searchAutoComplete(of('hello world 1')).subscribe()
    tick(250)
    expect(autocompleteSpy).toHaveBeenCalled()
  }))

  it('should support reset search field', () => {
    const resetSpy = jest.spyOn(component, 'resetSearchField')
    const input = (fixture.nativeElement as HTMLDivElement).querySelector(
      'input'
    ) as HTMLInputElement
    input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Escape' }))
    expect(resetSpy).toHaveBeenCalled()
  })

  it('should support choosing a search item', () => {
    expect(component.searchField.value).toEqual('')
    component.itemSelected({ item: 'hello', preventDefault: () => true })
    expect(component.searchField.value).toEqual('hello ')
    component.itemSelected({ item: 'world', preventDefault: () => true })
    expect(component.searchField.value).toEqual('hello world ')
  })

  it('should navigate via quickFilter on search', () => {
    const str = 'hello world '
    component.searchField.patchValue(str)
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.search()
    expect(qfSpy).toHaveBeenCalledWith([
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: str.trim(),
      },
    ])
  })
})
