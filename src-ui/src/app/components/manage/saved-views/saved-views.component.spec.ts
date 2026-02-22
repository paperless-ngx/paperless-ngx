import { DragDropModule } from '@angular/cdk/drag-drop'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { Subject, of, throwError } from 'rxjs'
import { SavedView } from 'src/app/data/saved-view'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
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
  let settingsService: SettingsService
  let toastService: ToastService
  let modalService: NgbModal

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
        ReactiveFormsModule,
        FormsModule,
        DragDropModule,
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
      providers: [
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
            currentUserHasObjectPermissions: () => true,
            currentUserOwnsObject: () => true,
          },
        },
        {
          provide: CustomFieldsService,
          useValue: {
            listAll: () =>
              of({
                all: [],
                count: 0,
                results: [],
              }),
          },
        },
        PermissionsGuard,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    savedViewService = TestBed.inject(SavedViewService)
    settingsService = TestBed.inject(SettingsService)
    toastService = TestBed.inject(ToastService)
    modalService = TestBed.inject(NgbModal)
    fixture = TestBed.createComponent(SavedViewsComponent)
    component = fixture.componentInstance

    jest.spyOn(savedViewService, 'list').mockReturnValue(
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
    const savedViewPatchSpy = jest.spyOn(savedViewService, 'patchMany')
    const control = component.savedViewsForm
      .get('savedViews')
      .get(savedViews[0].id.toString())
      .get('name')
    control.setValue(`${savedViews[0].name}-changed`)
    control.markAsDirty()

    // saved views error first
    savedViewPatchSpy.mockReturnValueOnce(
      throwError(() => new Error('unable to save saved views'))
    )
    component.save()
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(savedViewPatchSpy).toHaveBeenCalled()
    toastErrorSpy.mockClear()
    savedViewPatchSpy.mockClear()

    // succeed saved views
    savedViewPatchSpy.mockReturnValueOnce(of(savedViews as SavedView[]))
    control.setValue(savedViews[0].name)
    control.markAsDirty()
    component.save()
    expect(toastErrorSpy).not.toHaveBeenCalled()
    expect(savedViewPatchSpy).toHaveBeenCalled()
  })

  it('should update only patch saved views that have changed', () => {
    const patchSpy = jest.spyOn(savedViewService, 'patchMany')
    component.save()
    expect(patchSpy).not.toHaveBeenCalled()

    const view = savedViews[0]
    component.savedViewsForm
      .get('savedViews')
      .get(view.id.toString())
      .get('name')
      .setValue('changed-view-name')
    component.savedViewsForm
      .get('savedViews')
      .get(view.id.toString())
      .get('name')
      .markAsDirty()
    fixture.detectChanges()

    component.save()
    expect(patchSpy).toHaveBeenCalled()
    const patchBody = patchSpy.mock.calls[0][0][0]
    expect(patchBody).toMatchObject({
      id: view.id,
      name: 'changed-view-name',
    })
    expect(patchBody.show_on_dashboard).toBeUndefined()
    expect(patchBody.show_in_sidebar).toBeUndefined()
  })

  it('should persist visibility changes to user settings', () => {
    const patchSpy = jest.spyOn(savedViewService, 'patchMany')
    const updateVisibilitySpy = jest
      .spyOn(settingsService, 'updateSavedViewsVisibility')
      .mockReturnValue(of({ success: true }))

    const dashboardControl = component.savedViewsForm
      .get('savedViews')
      .get(savedViews[0].id.toString())
      .get('show_on_dashboard')
    dashboardControl.setValue(false)
    dashboardControl.markAsDirty()

    component.save()

    expect(patchSpy).not.toHaveBeenCalled()
    expect(updateVisibilitySpy).toHaveBeenCalledWith([], [savedViews[0].id])
  })

  it('should skip model updates for views that cannot be edited', () => {
    const patchSpy = jest.spyOn(savedViewService, 'patchMany')
    const updateVisibilitySpy = jest.spyOn(
      settingsService,
      'updateSavedViewsVisibility'
    )
    const nameControl = component.savedViewsForm
      .get('savedViews')
      .get(savedViews[0].id.toString())
      .get('name')

    nameControl.disable()

    component.save()

    expect(patchSpy).not.toHaveBeenCalled()
    expect(updateVisibilitySpy).not.toHaveBeenCalled()
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
    component.savedViewsForm
      .get('savedViews')
      .get(view.id.toString())
      .get('show_on_dashboard')
      .setValue(!view.show_on_dashboard)
    component.reset()
    expect(
      component.savedViewsForm
        .get('savedViews')
        .get(view.id.toString())
        .get('show_on_dashboard').value
    ).toEqual(view.show_on_dashboard)
  })

  it('should support editing permissions', () => {
    const confirmClicked = new Subject<any>()
    const modalRef = {
      componentInstance: {
        confirmClicked,
        buttonsEnabled: true,
      },
      close: jest.fn(),
    } as any
    jest.spyOn(modalService, 'open').mockReturnValue(modalRef)
    const patchSpy = jest.spyOn(savedViewService, 'patch')
    patchSpy.mockReturnValue(of(savedViews[0] as SavedView))

    component.editPermissions(savedViews[0] as SavedView)
    confirmClicked.next({
      permissions: {
        owner: 1,
        set_permissions: {
          view: { users: [2], groups: [] },
          change: { users: [], groups: [3] },
        },
      },
      merge: true,
    })

    expect(patchSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        id: savedViews[0].id,
        owner: 1,
        set_permissions: {
          view: { users: [2], groups: [] },
          change: { users: [], groups: [3] },
        },
      })
    )
    expect(modalRef.close).toHaveBeenCalled()
  })
})
