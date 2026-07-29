import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { of, throwError } from 'rxjs'
import { CustomFieldDataType } from 'src/app/data/custom-field'
import {
  CSV_EXPORT_CUSTOM_FIELDS_STORAGE_KEY,
  CSV_EXPORT_FIELDS_STORAGE_KEY,
  DEFAULT_CSV_EXPORT_FIELDS,
} from 'src/app/data/document'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ExportCsvDialogComponent } from './export-csv-dialog.component'

describe('ExportCsvDialogComponent', () => {
  let component: ExportCsvDialogComponent
  let fixture: ComponentFixture<ExportCsvDialogComponent>
  let documentService: DocumentService
  let customFieldsService: CustomFieldsService
  let permissionsService: PermissionsService
  let settingsService: SettingsService
  let activeModal: NgbActiveModal

  beforeEach(async () => {
    localStorage.clear()

    TestBed.configureTestingModule({
      imports: [ExportCsvDialogComponent],
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    documentService = TestBed.inject(DocumentService)
    customFieldsService = TestBed.inject(CustomFieldsService)
    permissionsService = TestBed.inject(PermissionsService)
    settingsService = TestBed.inject(SettingsService)
    activeModal = TestBed.inject(NgbActiveModal)

    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest.spyOn(settingsService, 'get').mockImplementation((key) => {
      if (key === SETTINGS_KEYS.NOTES_ENABLED) {
        return true
      }
      return null
    })
    jest.spyOn(customFieldsService, 'listAll').mockReturnValue(
      of({
        count: 2,
        all: [1, 2],
        results: [
          {
            id: 1,
            name: 'Amount',
            data_type: CustomFieldDataType.Monetary,
          },
          {
            id: 2,
            name: 'Vendor',
            data_type: CustomFieldDataType.String,
          },
        ],
      })
    )

    fixture = TestBed.createComponent(ExportCsvDialogComponent)
    component = fixture.componentInstance
    component.selection = { documents: [3, 4] }
    component.selectionCount = 2
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('should initialize with default document fields and load custom fields', () => {
    fixture.detectChanges()

    expect(component.documentFields.length).toBeGreaterThan(0)
    expect(component.customFields).toHaveLength(2)
    expect(component.hasSelection).toBeTruthy()
    for (const field of DEFAULT_CSV_EXPORT_FIELDS) {
      expect(component.selectedDocumentFields.has(field)).toBeTruthy()
    }
  })

  it('should show how many documents will be exported', () => {
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain(
      '2 documents will be exported.'
    )
  })

  it('should show the singular selection count for a single document', () => {
    component.selectionCount = 1
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain(
      'One document will be exported.'
    )
  })

  it('should show a zero selection count', () => {
    component.selectionCount = 0
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain(
      '0 documents will be exported.'
    )
  })

  it('should omit the selection count when it is unknown', () => {
    component.selectionCount = undefined
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).not.toContain('will be exported')
  })

  it('should restore saved document and custom field selections', () => {
    localStorage.setItem(
      CSV_EXPORT_FIELDS_STORAGE_KEY,
      JSON.stringify(['title', 'filename', 'unknown_field'])
    )
    localStorage.setItem(
      CSV_EXPORT_CUSTOM_FIELDS_STORAGE_KEY,
      JSON.stringify([1, 99])
    )

    fixture.detectChanges()

    expect(component.selectedDocumentFields.has('title')).toBeTruthy()
    expect(component.selectedDocumentFields.has('filename')).toBeTruthy()
    expect(component.selectedDocumentFields.has('unknown_field')).toBeFalsy()
    expect(component.selectedCustomFields.has(1)).toBeTruthy()
    expect(component.selectedCustomFields.has(99)).toBeFalsy()
  })

  it('should fall back to defaults when saved document fields are invalid JSON', () => {
    localStorage.setItem(CSV_EXPORT_FIELDS_STORAGE_KEY, '{not-json')

    fixture.detectChanges()

    for (const field of DEFAULT_CSV_EXPORT_FIELDS) {
      expect(component.selectedDocumentFields.has(field)).toBeTruthy()
    }
  })

  it('should ignore invalid saved custom field JSON', () => {
    localStorage.setItem(CSV_EXPORT_CUSTOM_FIELDS_STORAGE_KEY, '{not-json')

    fixture.detectChanges()

    expect(component.selectedCustomFields.size).toEqual(0)
  })

  it('should hide notes when notes are disabled', () => {
    ;(settingsService.get as jest.Mock).mockImplementation((key) => {
      if (key === SETTINGS_KEYS.NOTES_ENABLED) {
        return false
      }
      return null
    })

    fixture.detectChanges()

    expect(
      component.documentFields.some((field) => field.id === 'note')
    ).toBeFalsy()
  })

  it('should hide permission-gated fields when user lacks view permission', () => {
    ;(permissionsService.currentUserCan as jest.Mock).mockReturnValue(false)

    fixture.detectChanges()

    expect(
      component.documentFields.some((field) => field.id === 'correspondent')
    ).toBeFalsy()
    expect(
      component.documentFields.some((field) => field.id === 'title')
    ).toBeTruthy()
    expect(component.customFields).toHaveLength(0)
  })

  it('should toggle document and custom fields', () => {
    fixture.detectChanges()

    component.toggleDocumentField('title')
    expect(component.selectedDocumentFields.has('title')).toBeFalsy()
    component.toggleDocumentField('title')
    expect(component.selectedDocumentFields.has('title')).toBeTruthy()

    component.toggleCustomField(1)
    expect(component.selectedCustomFields.has(1)).toBeTruthy()
    component.toggleCustomField(1)
    expect(component.selectedCustomFields.has(1)).toBeFalsy()
  })

  it('should select all and none for document and custom fields', () => {
    fixture.detectChanges()

    component.selectAllDocumentFields()
    expect(component.selectedDocumentFields.size).toEqual(
      component.documentFields.length
    )
    component.selectNoDocumentFields()
    expect(component.selectedDocumentFields.size).toEqual(0)

    component.selectAllCustomFields()
    expect(component.selectedCustomFields.size).toEqual(2)
    component.selectNoCustomFields()
    expect(component.selectedCustomFields.size).toEqual(0)
  })

  it('should not export when nothing is selected', () => {
    fixture.detectChanges()
    const exportSpy = jest.spyOn(documentService, 'bulkExportCsv')

    component.selectNoDocumentFields()
    component.selectNoCustomFields()
    component.export()

    expect(exportSpy).not.toHaveBeenCalled()
  })

  it('should export CSV, persist selection, emit success and close modal', () => {
    fixture.detectChanges()
    const blob = new Blob(['csv'])
    const exportSpy = jest
      .spyOn(documentService, 'bulkExportCsv')
      .mockReturnValue(of(blob))
    const successSpy = jest.spyOn(component.succeeded, 'emit')
    const closeSpy = jest.spyOn(activeModal, 'close')

    component.selectedDocumentFields = new Set(['title', 'filename'])
    component.selectedCustomFields = new Set([1])
    component.export()

    expect(exportSpy).toHaveBeenCalledWith(
      { documents: [3, 4] },
      ['title', 'filename'],
      [1]
    )
    expect(
      JSON.parse(localStorage.getItem(CSV_EXPORT_FIELDS_STORAGE_KEY))
    ).toEqual(['title', 'filename'])
    expect(
      JSON.parse(localStorage.getItem(CSV_EXPORT_CUSTOM_FIELDS_STORAGE_KEY))
    ).toEqual([1])
    expect(successSpy).toHaveBeenCalledWith(blob)
    expect(closeSpy).toHaveBeenCalled()
    expect(component.exporting).toBeFalsy()
  })

  it('should emit failed on export error', () => {
    fixture.detectChanges()
    const error = new Error('export failed')
    jest
      .spyOn(documentService, 'bulkExportCsv')
      .mockReturnValue(throwError(() => error))
    const failSpy = jest.spyOn(component.failed, 'emit')

    component.export()

    expect(failSpy).toHaveBeenCalledWith(error)
    expect(component.exporting).toBeFalsy()
  })

  it('should dismiss modal on cancel', () => {
    const dismissSpy = jest.spyOn(activeModal, 'dismiss')
    component.cancel()
    expect(dismissSpy).toHaveBeenCalled()
  })
})
