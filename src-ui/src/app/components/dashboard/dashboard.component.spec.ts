import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbAlertModule } from '@ng-bootstrap/ng-bootstrap'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { DashboardComponent } from './dashboard.component'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { SettingsService } from 'src/app/services/settings.service'
import { StatisticsWidgetComponent } from './widgets/statistics-widget/statistics-widget.component'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { WidgetFrameComponent } from './widgets/widget-frame/widget-frame.component'
import { UploadFileWidgetComponent } from './widgets/upload-file-widget/upload-file-widget.component'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { By } from '@angular/platform-browser'
import { SavedViewWidgetComponent } from './widgets/saved-view-widget/saved-view-widget.component'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { RouterTestingModule } from '@angular/router/testing'
import { TourNgBootstrapModule, TourService } from 'ngx-ui-tour-ng-bootstrap'
import { LogoComponent } from '../common/logo/logo.component'
import { of, throwError } from 'rxjs'
import { ToastService } from 'src/app/services/toast.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { CdkDragDrop, DragDropModule } from '@angular/cdk/drag-drop'
import { SavedView } from 'src/app/data/saved-view'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
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
    show_in_sidebar: false,
    sort_field: 'name',
    sort_reverse: true,
    filter_rules: [],
  },
  {
    name: 'Saved View 3',
    id: 3,
    show_on_dashboard: true,
    show_in_sidebar: false,
    sort_field: 'name',
    sort_reverse: true,
    filter_rules: [],
  },
]

describe('DashboardComponent', () => {
  let component: DashboardComponent
  let fixture: ComponentFixture<DashboardComponent>
  let settingsService: SettingsService
  let tourService: TourService
  let toastService: ToastService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        DashboardComponent,
        StatisticsWidgetComponent,
        PageHeaderComponent,
        WidgetFrameComponent,
        UploadFileWidgetComponent,
        IfPermissionsDirective,
        SavedViewWidgetComponent,
        LogoComponent,
      ],
      imports: [
        NgbAlertModule,
        RouterTestingModule,
        TourNgBootstrapModule,
        DragDropModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        PermissionsGuard,
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
          },
        },
        {
          provide: SavedViewService,
          useValue: {
            listAll: () =>
              of({
                all: [saved_views.map((v) => v.id)],
                count: saved_views.length,
                results: saved_views,
              }),
            dashboardViews: saved_views.filter((v) => v.show_on_dashboard),
          },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = {
      first_name: 'Foo',
      last_name: 'Bar',
    }
    jest.spyOn(settingsService, 'get').mockImplementation((key) => {
      if (key === SETTINGS_KEYS.DASHBOARD_VIEWS_SORT_ORDER) return [0, 2, 3]
    })
    tourService = TestBed.inject(TourService)
    toastService = TestBed.inject(ToastService)
    fixture = TestBed.createComponent(DashboardComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should show a welcome message', () => {
    expect(component.subtitle).toEqual(`Hello Foo, welcome to Paperless-ngx`)
    settingsService.currentUser = {
      id: 1,
    }
    expect(component.subtitle).toEqual(`Welcome to Paperless-ngx`)
  })

  it('should show dashboard widgets', () => {
    expect(
      fixture.debugElement.queryAll(By.directive(SavedViewWidgetComponent))
    ).toHaveLength(saved_views.filter((v) => v.show_on_dashboard).length)
  })

  it('should end tour service if still running and welcome widget dismissed', () => {
    jest.spyOn(tourService, 'getStatus').mockReturnValueOnce(1)
    const endSpy = jest.spyOn(tourService, 'end')
    component.completeTour()
    expect(endSpy).toHaveBeenCalled()
  })

  it('should save tour completion if it was stopped and welcome widget dismissed', () => {
    jest.spyOn(tourService, 'getStatus').mockReturnValueOnce(0)
    const settingsCompleteTourSpy = jest.spyOn(settingsService, 'completeTour')
    component.completeTour()
    expect(settingsCompleteTourSpy).toHaveBeenCalled()
  })

  it('should disable global dropzone on start drag + drop, re-enable after', () => {
    expect(settingsService.globalDropzoneEnabled).toBeTruthy()
    component.onDragStart(null)
    expect(settingsService.globalDropzoneEnabled).toBeFalsy()
    component.onDragEnd(null)
    expect(settingsService.globalDropzoneEnabled).toBeTruthy()
  })

  it('should update saved view sorting on drag + drop, show info', () => {
    const settingsSpy = jest.spyOn(settingsService, 'updateDashboardViewsSort')
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
      if (key === SETTINGS_KEYS.DASHBOARD_VIEWS_SORT_ORDER) return []
    })
    fixture.destroy()
    fixture = TestBed.createComponent(DashboardComponent)
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
})
