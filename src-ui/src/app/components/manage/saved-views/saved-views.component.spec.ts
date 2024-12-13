import { DragDropModule } from '@angular/cdk/drag-drop'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { SavedView } from 'src/app/data/saved-view'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { PermissionsService } from 'src/app/services/permissions.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmButtonComponent } from '../../common/confirm-button/confirm-button.component'
import { CheckComponent } from '../../common/input/check/check.component'
import { DragDropSelectComponent } from '../../common/input/drag-drop-select/drag-drop-select.component'
import { NumberComponent } from '../../common/input/number/number.component'
import { SelectComponent } from '../../common/input/select/select.component'
import { TextComponent } from '../../common/input/text/text.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { SavedViewsComponent } from './saved-views.component'

const savedViews = [
  { id: 1, name: 'view1', show_in_sidebar: true, show_on_dashboard: true },
  { id: 2, name: 'view2', show_in_sidebar: false, show_on_dashboard: false },
]

describe('SavedViewsComponent', () => {
  let component: SavedViewsComponent
  let fixture: ComponentFixture<SavedViewsComponent>
  let savedViewService: SavedViewService
  let toastService: ToastService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        SavedViewsComponent,
        PageHeaderComponent,
        IfPermissionsDirective,
        CheckComponent,
        SelectComponent,
        TextComponent,
        NumberComponent,
        ConfirmButtonComponent,
        DragDropSelectComponent,
      ],
      imports: [
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
        ReactiveFormsModule,
        FormsModule,
        DragDropModule,
      ],
      providers: [
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
          },
        },
        PermissionsGuard,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    savedViewService = TestBed.inject(SavedViewService)
    toastService = TestBed.inject(ToastService)
    fixture = TestBed.createComponent(SavedViewsComponent)
    component = fixture.componentInstance

    jest.spyOn(savedViewService, 'listAll').mockReturnValue(
      of({
        all: savedViews.map((v) => v.id),
        count: savedViews.length,
        results: (savedViews as SavedView[]).concat([]),
      })
    )

    fixture.detectChanges()
  })

  it('should support save saved views, show error', () => {
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
    component.save()
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(savedViewPatchSpy).toHaveBeenCalled()
    toastSpy.mockClear()
    toastErrorSpy.mockClear()
    savedViewPatchSpy.mockClear()

    // succeed saved views
    savedViewPatchSpy.mockReturnValueOnce(of(savedViews as SavedView[]))
    component.save()
    expect(toastErrorSpy).not.toHaveBeenCalled()
    expect(savedViewPatchSpy).toHaveBeenCalled()
  })

  it('should update only patch saved views that have changed', () => {
    const patchSpy = jest.spyOn(savedViewService, 'patchMany')
    component.save()
    expect(patchSpy).not.toHaveBeenCalled()

    const view = savedViews[0]
    const toggle = fixture.debugElement.query(
      By.css('.form-check.form-switch input')
    )
    toggle.nativeElement.checked = true
    toggle.nativeElement.dispatchEvent(new Event('change'))
    // register change
    component.savedViewsForm.get('savedViews').get(view.id.toString()).value[
      'show_on_dashboard'
    ] = !view.show_on_dashboard
    fixture.detectChanges()

    component.save()
    expect(patchSpy).toHaveBeenCalledWith([
      {
        id: view.id,
        name: view.name,
        show_in_sidebar: view.show_in_sidebar,
        show_on_dashboard: !view.show_on_dashboard,
      },
    ])
  })

  it('should support delete saved view', () => {
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    const deleteSpy = jest.spyOn(savedViewService, 'delete')
    deleteSpy.mockReturnValue(of(true))
    component.deleteSavedView(savedViews[0] as SavedView)
    expect(deleteSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith(
      `Saved view "${savedViews[0].name}" deleted.`
    )
  })

  it('should support reset', () => {
    const view = savedViews[0]
    component.savedViewsForm.get('savedViews').get(view.id.toString()).value[
      'show_on_dashboard'
    ] = !view.show_on_dashboard
    component.reset()
    expect(
      component.savedViewsForm.get('savedViews').get(view.id.toString()).value[
        'show_on_dashboard'
      ]
    ).toEqual(view.show_on_dashboard)
  })
})
