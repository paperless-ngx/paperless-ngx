import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbAlertModule, NgbAlert } from '@ng-bootstrap/ng-bootstrap'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { DashboardComponent } from './dashboard.component'
import { HttpClientTestingModule } from '@angular/common/http/testing'
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
import { NgxFileDropModule } from 'ngx-file-drop'
import { RouterTestingModule } from '@angular/router/testing'
import { TourNgBootstrapModule, TourService } from 'ngx-ui-tour-ng-bootstrap'

describe('DashboardComponent', () => {
  let component: DashboardComponent
  let fixture: ComponentFixture<DashboardComponent>
  let settingsService: SettingsService
  let tourService: TourService

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
            dashboardViews: [
              {
                id: 1,
                name: 'saved view 1',
                show_on_dashboard: true,
                sort_field: 'added',
                sort_reverse: true,
                filter_rules: [],
              },
              {
                id: 2,
                name: 'saved view 2',
                show_on_dashboard: true,
                sort_field: 'created',
                sort_reverse: true,
                filter_rules: [],
              },
            ],
          },
        },
      ],
      imports: [
        NgbAlertModule,
        HttpClientTestingModule,
        NgxFileDropModule,
        RouterTestingModule,
        TourNgBootstrapModule,
      ],
    }).compileComponents()

    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = {
      first_name: 'Foo',
      last_name: 'Bar',
    }
    tourService = TestBed.inject(TourService)
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
    ).toHaveLength(2)
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
})
