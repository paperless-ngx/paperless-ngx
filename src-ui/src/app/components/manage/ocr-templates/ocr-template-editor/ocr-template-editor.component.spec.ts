import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ElementRef } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { NgbActiveModal, NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { of, Subject, throwError } from 'rxjs'
import { PermissionsFormComponent } from 'src/app/components/common/input/permissions/permissions-form/permissions-form.component'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { Document } from 'src/app/data/document'
import {
  MATCH_ANY,
  MATCH_AUTO,
  MATCH_LITERAL,
  MATCH_NONE,
} from 'src/app/data/matching-model'
import {
  OcrTemplate,
  OcrTemplateZone,
  OcrZoneTarget,
  OcrZoneTestResult,
  OcrZoneTransform,
} from 'src/app/data/ocr-template'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { User } from 'src/app/data/user'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { OcrTemplateEditorComponent } from './ocr-template-editor.component'

const customFields: CustomField[] = [
  { id: 1, name: 'Invoice number', data_type: CustomFieldDataType.String },
  { id: 2, name: 'Status', data_type: CustomFieldDataType.Select },
]

function zone(overrides: Partial<OcrTemplateZone> = {}): OcrTemplateZone {
  return {
    name: 'Invoice number',
    target: OcrZoneTarget.CustomField,
    custom_field: 1,
    x: 100,
    y: 100,
    width: 200,
    height: 100,
    page: 1,
    ocr_language: 'eng',
    transform: OcrZoneTransform.Strip,
    validation_regex: '',
    order: 0,
    ...overrides,
  }
}

function pointer(x: number, y: number, pointerId = 1): PointerEvent {
  return Object.assign(
    new MouseEvent('pointermove', { clientX: x, clientY: y, button: 0 }),
    { pointerId }
  ) as PointerEvent
}

describe('OcrTemplateEditorComponent', () => {
  let component: OcrTemplateEditorComponent
  let fixture: ComponentFixture<OcrTemplateEditorComponent>
  let documentService: DocumentService
  let templateService: OcrTemplateService
  let modalService: NgbModal
  const activeModal = { close: jest.fn(), dismiss: jest.fn() }

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        NgxBootstrapIconsModule.pick(allIcons),
        OcrTemplateEditorComponent,
      ],
      providers: [
        { provide: NgbActiveModal, useValue: activeModal },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
    jest
      .spyOn(TestBed.inject(CustomFieldsService), 'listAll')
      .mockReturnValue(of({ count: 2, all: [1, 2], results: customFields }))
    jest
      .spyOn(TestBed.inject(UserService), 'listAll')
      .mockReturnValue(of({ count: 0, all: [], results: [] }))
    TestBed.inject(PermissionsService).initialize([], { id: 1 } as User)
    documentService = TestBed.inject(DocumentService)
    jest
      .spyOn(documentService, 'get')
      .mockReturnValue(of({ id: 5, page_count: 3 }))
    templateService = TestBed.inject(OcrTemplateService)
    modalService = TestBed.inject(NgbModal)
    activeModal.close.mockReset()
    fixture = TestBed.createComponent(OcrTemplateEditorComponent)
    component = fixture.componentInstance
  })

  function prepareOverlay() {
    const image = document.createElement('img')
    Object.defineProperties(image, {
      naturalWidth: { value: 1000 },
      naturalHeight: { value: 1000 },
      clientWidth: { value: 1000 },
    })
    const overlay = document.createElementNS(
      'http://www.w3.org/2000/svg',
      'svg'
    )
    Object.assign(overlay, {
      getScreenCTM: () => ({ inverse: () => ({}) }),
      createSVGPoint: () => ({
        x: 0,
        y: 0,
        matrixTransform() {
          return { x: this.x, y: this.y }
        },
      }),
      setPointerCapture: jest.fn(),
      hasPointerCapture: () => true,
      releasePointerCapture: jest.fn(),
    })
    component.imageRef = new ElementRef(image)
    component.overlayRef = new ElementRef(overlay)
    component.pageLoaded.set(true)
  }

  function fieldDialog() {
    const dialog = {
      dialogMode: { set: jest.fn() },
      object: null,
      succeeded: new Subject<CustomField>(),
      failed: new Subject(),
    }
    jest
      .spyOn(modalService, 'open')
      .mockReturnValue({ componentInstance: dialog } as any)
    return dialog
  }

  it('updates screen-sized overlay units when the preview image resizes', () => {
    let resize: ResizeObserverCallback
    const observer = {
      observe: jest.fn(),
      unobserve: jest.fn(),
      disconnect: jest.fn(),
    }
    const resizeObserver = jest
      .spyOn(globalThis, 'ResizeObserver')
      .mockImplementation((callback) => {
        resize = callback
        return observer
      })
    const image = document.createElement('img')
    const ref = new ElementRef(image)
    component.pageImage = ref
    expect(observer.observe).toHaveBeenCalledWith(image)
    resize([], observer)
    expect(component.overlayUnitSize(8)).toBe(8)

    Object.defineProperties(image, {
      naturalWidth: { value: 1000 },
      clientWidth: { value: 500 },
    })
    resize([], observer)
    expect(component.overlayUnitSize(8)).toBe(16)
    expect(component.overlayFontSize()).toBe(24)

    component.pageImage = undefined
    expect(observer.disconnect).toHaveBeenCalledTimes(1)
    fixture.destroy()
    expect(observer.disconnect).toHaveBeenCalledTimes(2)
    resizeObserver.mockRestore()
  })

  it('renders loaded image dimensions, zone labels, and selection handles', () => {
    component.object = {
      ...component.template,
      id: 3,
      sample_document: 5,
      zones: [zone()],
    }
    component.selectedZoneIndex = 0
    fixture.detectChanges()
    const image = fixture.nativeElement.querySelector('img')
    Object.defineProperties(image, {
      naturalWidth: { value: 1000 },
      naturalHeight: { value: 1500 },
    })
    image.dispatchEvent(new Event('load'))
    fixture.detectChanges()

    expect(component.template).toMatchObject({
      source_width: 1000,
      source_height: 1500,
    })
    expect(
      fixture.nativeElement
        .querySelector('.zone-overlay')
        .getAttribute('viewBox')
    ).toBe('0 0 1000 1500')
    expect(
      fixture.nativeElement.querySelector('.zone-label').textContent
    ).toContain('Invoice number')
    expect(
      fixture.nativeElement.querySelectorAll('.zone-resize-handle')
    ).toHaveLength(8)
    expect(component.zoneLabel(zone({ name: '' }), 2)).toBe('Zone 3')
    expect(component.zoneLabelY({ x: 0, y: 0, w: 100, h: 100 })).toBe(14)
  })

  it('offers the supported language and transform choices', () => {
    expect(component.languageOptions.map((option) => option.id)).toContain(
      'eng'
    )
    expect(component.transformOptions.map((option) => option.id)).toEqual(
      Object.values(OcrZoneTransform)
    )
  })

  it('clamps page navigation and supports one-based page input', () => {
    component.setSampleDocument([5])
    component.previewPageDisplay = 2
    expect(component.previewPage).toBe(1)
    expect(component.previewPageDisplay).toBe(2)
    expect(component.pageImageUrl).toContain('/5/1/')
    component.pageLoaded.set(true)
    component.goToPage(1)
    expect(component.pageLoaded()).toBe(true)
    component.goToPage(Infinity)
    component.goToPage(NaN)
    expect(component.previewPage).toBe(1)
    component.goToPage(99)
    expect(component.previewPage).toBe(2)
    expect(component.pageLoaded()).toBe(false)
    component.goToPage(-5)
    expect(component.previewPage).toBe(0)
    component.previewPageCount.set(null)
    component.goToPage(4.7)
    expect(component.previewPage).toBe(4)
  })

  it('limits zoom and resets it to the original size', () => {
    for (let i = 0; i < 20; i++) component.zoomIn()
    expect(component.zoom).toBe(4)
    for (let i = 0; i < 20; i++) component.zoomOut()
    expect(component.zoom).toBe(0.5)
    component.resetZoom()
    expect(component.zoom).toBe(1)
  })

  it('moves last-page zones to the last page and can pin them to a page', () => {
    component.setSampleDocument([5])
    const selected = zone()
    component.template.zones = [selected]
    expect(component.isLastPageZone(selected)).toBe(false)
    component.setLastPageZone(selected, true)
    expect(selected.page).toBe(-1)
    expect(component.isLastPageZone(selected)).toBe(true)
    component.selectZone(0)
    expect(component.previewPage).toBe(2)
    component.setLastPageZone(selected, false)
    expect(selected.page).toBe(3)
  })

  it('ignores page-count errors from a previous sample document', () => {
    const pending = new Subject<Document>()
    jest
      .spyOn(documentService, 'get')
      .mockReturnValueOnce(pending)
      .mockReturnValueOnce(of({ id: 6 }))
    component.setSampleDocument([5])
    component.setSampleDocument([6])
    pending.error(new Error('Old document failed'))
    expect(component.pageFailed()).toBe(false)
    expect(component.previewPageCount()).toBeNull()
  })

  it('ignores non-primary, unloaded, and saving pointer gestures', () => {
    prepareOverlay()
    component.onOverlayPointerDown(
      new MouseEvent('pointerdown', { button: 2 }) as PointerEvent
    )
    expect(component.drawingRect()).toBeNull()
    component.pageLoaded.set(false)
    component.onOverlayPointerDown(pointer(100, 100))
    expect(component.drawingRect()).toBeNull()
    component.pageLoaded.set(true)
    component.saving.set(true)
    component.onOverlayPointerDown(pointer(100, 100))
    expect(component.drawingRect()).toBeNull()
  })

  it('ignores pointer events when the SVG coordinate transform is unavailable', () => {
    component.onOverlayPointerDown(pointer(100, 100))
    expect(component.drawingRect()).toBeNull()
    prepareOverlay()
    jest
      .spyOn(component.overlayRef.nativeElement, 'getScreenCTM')
      .mockReturnValue(null)
    component.onOverlayPointerDown(pointer(100, 100))
    component.onOverlayPointerMove(pointer(200, 200))
    expect(component.drawingRect()).toBeNull()
  })

  it('updates a drawing only for its captured pointer', () => {
    prepareOverlay()
    component.onOverlayPointerDown(pointer(100, 100))
    component.onOverlayPointerDown(pointer(500, 500, 2))
    component.onOverlayPointerMove(pointer(900, 900, 2))
    expect(component.drawingRect()).toEqual({ x: 100, y: 100, w: 0, h: 0 })
    component.onOverlayPointerMove(pointer(250, 200))
    expect(component.drawingRect()).toEqual({ x: 100, y: 100, w: 150, h: 100 })
    component.onOverlayPointerUp(pointer(250, 200))
    expect(component.template.zones[0]).toMatchObject({
      x: 100,
      y: 100,
      width: 150,
      height: 100,
    })
  })

  it('resizes a selected zone using its corner handle', () => {
    prepareOverlay()
    const selected = zone()
    component.template.zones = [selected]
    component.selectZone(0)
    component.onOverlayPointerDown(pointer(100, 100))
    component.onOverlayPointerMove(pointer(50, 75))
    component.onOverlayPointerUp(pointer(60, 80))
    expect(selected).toMatchObject({ x: 60, y: 80, width: 240, height: 120 })
    expect(component.template.zones).toHaveLength(1)
  })

  it('shows the appropriate cursor over handles, zones, and empty space', () => {
    prepareOverlay()
    component.template.zones = [zone()]
    component.onOverlayPointerMove(pointer(150, 150))
    expect(component.overlayCursor).toBe('move')
    component.selectZone(0)
    component.onOverlayPointerMove(pointer(100, 100))
    expect(component.overlayCursor).toBe('nw-resize')
    component.onOverlayPointerMove(pointer(500, 500))
    expect(component.overlayCursor).toBe('crosshair')
    component.template.zones[0].page = 2
    component.onOverlayPointerMove(pointer(100, 100))
    expect(component.zoneDisplayRect(0)).toBeNull()
    expect(component.overlayCursor).toBe('crosshair')
  })

  it('cancels only the captured pointer and tolerates an already-lost capture', () => {
    prepareOverlay()
    component.onOverlayPointerCancel(pointer(100, 100))
    component.onOverlayPointerDown(pointer(100, 100))
    component.onOverlayPointerCancel(pointer(150, 150, 2))
    expect(component.drawingRect()).not.toBeNull()
    jest
      .spyOn(component.overlayRef.nativeElement, 'hasPointerCapture')
      .mockReturnValue(false)
    component.onOverlayPointerCancel(pointer(150, 150))
    expect(component.drawingRect()).toBeNull()
    expect(
      component.overlayRef.nativeElement.releasePointerCapture
    ).not.toHaveBeenCalled()
    expect(component.template.zones).toEqual([])
  })

  it('preserves the selected zone when an earlier or later zone is removed', () => {
    component.template.zones = [zone(), zone(), zone(), zone()]
    component.selectZone(1)
    const selected = component.selectedZone
    component.removeZone(3)
    expect(component.selectedZone).toBe(selected)
    component.removeZone(0)
    expect(component.selectedZoneIndex).toBe(0)
    expect(component.selectedZone).toBe(selected)
    component.selectZone(99)
    expect(component.selectedZone).toBeNull()
  })

  it('does not test zones without a selection or a sample document', () => {
    const test = jest.spyOn(templateService, 'testZone')
    component.testZone()
    component.template.zones = [zone()]
    component.selectZone(0)
    component.testZone()
    expect(test).not.toHaveBeenCalled()
  })

  it.each([
    {
      response: { error: { error: 'OCR unavailable' } },
      message: 'OCR unavailable',
    },
    { response: new Error('Network failure'), message: 'Test failed' },
  ])('shows zone-test errors: $message', ({ response, message }) => {
    component.template.zones = [zone({ page: undefined })]
    component.selectZone(0)
    component.setSampleDocument([5])
    jest
      .spyOn(templateService, 'testZone')
      .mockReturnValue(throwError(() => response))
    component.testZone()
    expect(component.zoneTestResult).toEqual({ error: message })
    expect(component.zoneTesting).toBe(false)
    expect(templateService.testZone).toHaveBeenCalledWith(
      5,
      expect.objectContaining({ page: 1 })
    )
  })

  it('switches between built-in targets, custom fields, and an unassigned field', () => {
    const selected = zone()
    expect(component.zoneFieldValue(selected)).toBe(1)
    component.setZoneField(selected, OcrZoneTarget.Title)
    expect(component.zoneFieldValue(selected)).toBe(OcrZoneTarget.Title)
    expect(selected.custom_field).toBeNull()
    component.setZoneField(selected, 7)
    expect(selected).toMatchObject({
      target: OcrZoneTarget.CustomField,
      custom_field: 7,
    })
    component.setZoneField(selected, null)
    expect(component.zoneFieldValue(selected)).toBeNull()
    expect(component.zonesForField(selected)).toEqual([])
    component.setCombineFormat(selected, 'Ignored')
    expect(component.template.combine_formats).toEqual({})
  })

  it('creates combine formats when absent and leaves implicit formats alone on rename', () => {
    const selected = zone({ target: OcrZoneTarget.Title, custom_field: null })
    component.template.combine_formats = undefined
    component.renameZone(selected, 'Renamed')
    expect(selected.name).toBe('Renamed')
    expect(component.getCombineFormat(selected)).toBe('')
    component.setCombineFormat(selected, '{Renamed} ')
    component.insertCombineToken(selected, selected)
    expect(component.template.combine_formats).toEqual({
      title: '{Renamed} {Renamed}',
    })
  })

  it('saves templates without combine formats', () => {
    component.template.combine_formats = undefined
    fixture.detectChanges()
    expect(component.isDirty).toBe(false)
    jest
      .spyOn(templateService, 'create')
      .mockReturnValue(of(component.template))
    component.save()
    expect(component.template.combine_formats).toBeUndefined()
  })

  it('does not assign unsupported custom field types and surfaces creation failures', () => {
    component.template.zones = [zone({ custom_field: null })]
    component.selectZone(0)
    const dialog = fieldDialog()
    const error = jest.spyOn(TestBed.inject(ToastService), 'showError')
    component.createField('Status')
    expect(dialog.object).toEqual({ name: 'Status' })
    dialog.succeeded.next(customFields[1])
    expect(component.selectedZone.custom_field).toBeNull()
    const failure = new Error('Could not save')
    dialog.failed.next(failure)
    expect(error).toHaveBeenCalledWith('Error saving field.', failure)
  })

  it('refreshes field choices when a field is created without a selected zone', () => {
    const dialog = fieldDialog()
    component.createField('Total')
    dialog.succeeded.next(customFields[0])
    expect(component.customFields()).toEqual(customFields)
    expect(component.selectedZone).toBeNull()
  })

  it('should edit a copy of the template and load its sample document', () => {
    const original: OcrTemplate = {
      ...component.template,
      id: 3,
      name: 'Invoices',
      match: 'Northwind',
      matching_algorithm: MATCH_LITERAL,
      sample_document: 5,
      zones: [zone()],
      combine_formats: { '1': '{Invoice number}' },
    }
    component.object = original
    fixture.detectChanges()

    expect(component.dialogTitle).toEqual('Edit OCR Template')
    expect(component.previewDocId).toEqual(5)
    expect(component.previewPageCount()).toEqual(3)
    expect(component.pageImageUrl).toContain('document-page-image/5/0/')
    expect(component.template.match).toEqual('Northwind')
    expect(component.isDirty).toBeFalsy()

    component.template.zones[0].x = 500
    component.template.combine_formats['1'] = 'Edited'
    expect(original.zones[0].x).toEqual(100)
    expect(original.combine_formats['1']).toEqual('{Invoice number}')
  })

  it('should offer every matching algorithm except automatic', () => {
    expect(component.matchingAlgorithms.map((a) => a.id)).not.toContain(
      MATCH_AUTO
    )
    expect(component.template.matching_algorithm).toEqual(MATCH_ANY)
    expect(component.patternRequired).toBeTruthy()

    component.template.matching_algorithm = MATCH_NONE
    expect(component.patternRequired).toBeFalsy()
  })

  it('should initialize new template permissions from saved defaults', () => {
    const defaults = {
      [SETTINGS_KEYS.DEFAULT_PERMS_OWNER]: 1,
      [SETTINGS_KEYS.DEFAULT_PERMS_VIEW_USERS]: [2],
      [SETTINGS_KEYS.DEFAULT_PERMS_VIEW_GROUPS]: [3],
      [SETTINGS_KEYS.DEFAULT_PERMS_EDIT_USERS]: [],
      [SETTINGS_KEYS.DEFAULT_PERMS_EDIT_GROUPS]: [4],
    }
    jest
      .spyOn(TestBed.inject(SettingsService), 'get')
      .mockImplementation((key) => defaults[key])
    fixture.detectChanges()
    expect(component.permissionsForm).toEqual({
      owner: 1,
      set_permissions: {
        view: { users: [2], groups: [3] },
        change: { users: [], groups: [4] },
      },
    })
    expect(
      fixture.debugElement.query(By.directive(PermissionsFormComponent))
    ).toBeTruthy()
    expect(component.isDirty).toBe(false)
    const create = jest
      .spyOn(templateService, 'create')
      .mockReturnValue(of({ ...component.template, id: 3 }))
    component.save()
    expect(create).toHaveBeenCalledWith(
      expect.objectContaining(component.permissionsForm)
    )
  })

  it('should copy existing permissions and track changes without mutating the list item', () => {
    component.object = {
      ...component.template,
      id: 3,
      owner: 1,
      permissions: {
        view: { users: [2], groups: [] },
        change: { users: [], groups: [3] },
      },
    }
    fixture.detectChanges()
    expect(component.permissionsForm.owner).toBe(1)
    expect(component.isDirty).toBe(false)
    component.permissionsForm.set_permissions.view.users.push(4)
    expect(component.isDirty).toBe(true)
    expect(component.object.permissions.view.users).toEqual([2])
    const update = jest
      .spyOn(templateService, 'update')
      .mockReturnValue(of(component.template))
    component.save()
    expect(update).toHaveBeenCalledWith(
      expect.objectContaining({
        owner: 1,
        set_permissions: {
          view: { users: [2, 4], groups: [] },
          change: { users: [], groups: [3] },
        },
      })
    )
  })

  it('should hide sharing controls and omit permission changes for a shared editor', () => {
    component.object = {
      ...component.template,
      id: 3,
      owner: 2,
      user_can_change: true,
    }
    fixture.detectChanges()
    expect(
      fixture.debugElement.query(By.directive(PermissionsFormComponent))
    ).toBeNull()
    component.permissionsForm = {
      owner: 1,
      set_permissions: { view: { users: [1] } },
    }
    const update = jest
      .spyOn(templateService, 'update')
      .mockReturnValue(of(component.template))
    component.save()
    expect(update.mock.calls[0][0].owner).toBe(2)
    expect(update.mock.calls[0][0]).not.toHaveProperty('set_permissions')
  })

  it('should keep only the last picked sample document', () => {
    component.setSampleDocument([5, 6])
    expect(component.sampleDocumentIds).toEqual([6])

    component.setSampleDocument([])
    expect(component.previewDocId).toBeNull()
    expect(component.pageImageUrl).toBeNull()
  })

  it('should ignore a stale sample document response', () => {
    const pending = new Subject<Document>()
    jest.spyOn(documentService, 'get').mockReturnValueOnce(pending)
    component.setSampleDocument([5])
    component.setSampleDocument([6])
    pending.next({ id: 5, page_count: 99 })

    expect(component.previewPageCount()).toEqual(3)
  })

  it('should show a failed page and retry it', () => {
    jest
      .spyOn(documentService, 'get')
      .mockReturnValueOnce(throwError(() => new Error('offline')))
    component.setSampleDocument([5])
    expect(component.pageFailed()).toBeTruthy()

    component.setSampleDocument(component.sampleDocumentIds)
    expect(component.pageFailed()).toBeFalsy()

    component.onImageError()
    expect(component.pageFailed()).toBeTruthy()
  })

  it('should support create and update', () => {
    const createSpy = jest
      .spyOn(templateService, 'create')
      .mockReturnValue(of({ ...component.template, id: 3 }))
    const updateSpy = jest
      .spyOn(templateService, 'update')
      .mockReturnValue(of(component.template))
    const succeededSpy = jest.spyOn(component.succeeded, 'emit')

    component.save()
    expect(createSpy).toHaveBeenCalled()
    expect(succeededSpy).toHaveBeenCalledWith({ ...component.template, id: 3 })
    expect(activeModal.close).toHaveBeenCalled()

    component.saving.set(false)
    component.template.id = 3
    component.save()
    expect(updateSpy).toHaveBeenCalledWith(component.template)
  })

  it('should emit failed and allow editing again after a failed save', () => {
    prepareOverlay()
    component.template.zones = [zone()]
    const pending = new Subject<OcrTemplate>()
    jest.spyOn(templateService, 'create').mockReturnValue(pending)
    const failedSpy = jest.spyOn(component.failed, 'emit')
    component.onOverlayPointerDown(pointer(150, 150))

    component.save()
    component.save()
    expect(templateService.create).toHaveBeenCalledTimes(1)
    component.onOverlayPointerMove(pointer(250, 250))
    component.onOverlayPointerUp(pointer(250, 250))
    expect(component.template.zones[0].x).toEqual(100)

    pending.error(new Error('Save failed'))
    expect(failedSpy).toHaveBeenCalled()
    expect(component.saving()).toBeFalsy()
    component.onOverlayPointerDown(pointer(150, 150))
    component.onOverlayPointerUp(pointer(250, 250))
    expect(component.template.zones[0].x).toEqual(200)
  })

  it('should track unsaved changes', () => {
    fixture.detectChanges()
    expect(component.isDirty).toBeFalsy()

    component.template.combine_formats = { '1': '' }
    expect(component.isDirty).toBeFalsy()

    component.template.name = 'Invoices'
    expect(component.isDirty).toBeTruthy()
    component.template.name = ''
    expect(component.isDirty).toBeFalsy()

    component.setSampleDocument([5])
    expect(component.isDirty).toBeTruthy()
  })

  it('should draw a zone with no field in empty space', () => {
    prepareOverlay()
    component.onOverlayPointerDown(pointer(100, 100))
    component.onOverlayPointerUp(pointer(1200, 250))

    expect(component.template.zones[0]).toMatchObject({
      x: 100,
      y: 100,
      width: 900,
      height: 150,
      custom_field: null,
    })
    expect(component.selectedZoneIndex).toEqual(0)
  })

  it('should clear the selection on a click in empty space', () => {
    prepareOverlay()
    component.template.zones = [zone()]
    component.selectZone(0)
    component.onOverlayPointerDown(pointer(600, 600))
    component.onOverlayPointerUp(pointer(602, 601))

    expect(component.template.zones).toHaveLength(1)
    expect(component.selectedZoneIndex).toBeNull()
  })

  it('should move a zone when dragging on it', () => {
    prepareOverlay()
    component.template.zones = [zone()]
    component.onOverlayPointerDown(pointer(150, 150))
    component.onOverlayPointerUp(pointer(250, 200))

    expect(component.template.zones).toHaveLength(1)
    expect(component.template.zones[0]).toMatchObject({ x: 200, y: 150 })
  })

  it('should cancel a drawing on escape and ignore other pointers', () => {
    prepareOverlay()
    component.onOverlayPointerDown(pointer(100, 100))
    component.onOverlayPointerUp(pointer(300, 200, 2))
    expect(component.drawingRect()).not.toBeNull()

    component.cancelDrawing()
    component.onOverlayPointerUp(pointer(300, 200))
    expect(component.template.zones).toEqual([])
  })

  it('should open a zone in the zones tab and go back to the list', () => {
    component.template.zones = [zone(), zone()]
    component.selectZone(1)
    expect(component.activeTab).toEqual('zones')
    expect(component.selectedZone).toBe(component.template.zones[1])

    component.deselectZone()
    expect(component.selectedZone).toBeNull()

    component.selectZone(0)
    component.removeZone(0)
    expect(component.template.zones).toHaveLength(1)
    expect(component.selectedZone).toBeNull()
  })

  it('should only offer custom fields OCR can write to', () => {
    fixture.detectChanges()
    expect(component.fieldItems().map((item) => item.id)).toEqual([
      OcrZoneTarget.Title,
      OcrZoneTarget.Asn,
      OcrZoneTarget.Created,
      1,
    ])
  })

  it('should create a custom field and assign it to the zone', () => {
    const succeeded = new Subject<CustomField>()
    const dialog = {
      dialogMode: { set: jest.fn() },
      object: null,
      succeeded,
      failed: new Subject(),
    }
    jest
      .spyOn(modalService, 'open')
      .mockReturnValue({ componentInstance: dialog } as any)
    component.template.zones = [zone({ custom_field: null })]
    component.selectZone(0)

    component.createField()
    expect(dialog.object).toEqual({ name: 'Invoice number' })
    succeeded.next(customFields[0])

    expect(component.template.zones[0].custom_field).toEqual(1)
  })

  it('should build and prune combine formats', () => {
    const first = zone({ name: 'First' })
    const second = zone({ name: 'Second' })
    const other = zone({ name: 'Other', custom_field: 2 })
    component.template.zones = [first, second, other]
    component.template.combine_formats = { '2': '{Other}' }

    expect(component.isFieldShared(first)).toBeTruthy()
    expect(component.isFieldShared(other)).toBeFalsy()
    expect(component.defaultCombineFormat(first)).toEqual('{First} {Second}')

    component.insertCombineToken(first, second)
    component.insertCombineToken(first, first)
    expect(component.getCombineFormat(second)).toEqual('{Second} {First}')

    jest.spyOn(templateService, 'create').mockReturnValue(of(null))
    component.save()
    expect(component.template.combine_formats).toEqual({
      '1': '{Second} {First}',
    })
  })

  it('should update exact tokens when a zone is renamed', () => {
    const first = zone({ name: 'First [value]' })
    component.template.zones = [first, zone({ name: 'Second' })]
    component.template.combine_formats = {
      '1': 'First [value]: {First [value]} / { First [value] } / {Second} / {First [value] extra}',
      '2': '{First [value]}',
    }

    component.renameZone(first, '')
    component.renameZone(first, 'Invoice number')

    expect(first.name).toEqual('Invoice number')
    expect(component.template.combine_formats).toEqual({
      '1': 'First [value]: {Invoice number} / {Invoice number} / {Second} / {First [value] extra}',
      '2': '{First [value]}',
    })
  })

  it('should keep the language array stable until the value changes', () => {
    const selected = zone({ ocr_language: 'deu+eng' })
    const languages = component.ocrLanguageArray(selected)
    expect(languages).toEqual(['deu', 'eng'])
    expect(component.ocrLanguageArray(selected)).toBe(languages)

    component.setOcrLanguages(selected, ['fra'])
    expect(selected.ocr_language).toEqual('fra')
    expect(component.ocrLanguageArray(selected)).toEqual(['fra'])

    component.setOcrLanguages(selected, null)
    expect(component.ocrLanguageArray(selected)).toEqual([])
  })

  it('should hide a test result once the zone changes', () => {
    const selected = zone()
    component.template.zones = [selected]
    component.selectZone(0)
    component.setSampleDocument([5])
    jest
      .spyOn(templateService, 'testZone')
      .mockReturnValue(of({ value: '123' }))

    component.testZone()
    expect(component.zoneTestResult.value).toEqual('123')

    selected.transform = OcrZoneTransform.Numeric
    expect(component.zoneTestResult).toBeNull()
  })

  it('should drop a pending test when the zone or sample document changes', () => {
    const pending = new Subject<OcrZoneTestResult>()
    component.template.zones = [zone(), zone()]
    component.selectZone(0)
    component.setSampleDocument([5])
    jest.spyOn(templateService, 'testZone').mockReturnValue(pending)

    component.testZone()
    expect(component.zoneTesting).toBeTruthy()
    component.selectZone(1)
    pending.next({ value: 'Old zone' })
    expect(component.zoneTestResult).toBeNull()

    component.testZone()
    component.setSampleDocument([])
    pending.next({ value: 'Old document' })
    expect(component.zoneTestResult).toBeNull()
  })
})
