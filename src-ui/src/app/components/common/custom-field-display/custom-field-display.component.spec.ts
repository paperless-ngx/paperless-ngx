import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { of } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { DisplayField, Document } from 'src/app/data/document'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { CustomFieldDisplayComponent } from './custom-field-display.component'

const customFields: CustomField[] = [
  { id: 1, name: 'Field 1', data_type: CustomFieldDataType.String },
  { id: 2, name: 'Field 2', data_type: CustomFieldDataType.Monetary },
  { id: 3, name: 'Field 3', data_type: CustomFieldDataType.DocumentLink },
  {
    id: 4,
    name: 'Field 4',
    data_type: CustomFieldDataType.Select,
    extra_data: {
      select_options: [
        { label: 'Option 1', id: 'abc-123' },
        { label: 'Option 2', id: 'def-456' },
        { label: 'Option 3', id: 'ghi-789' },
      ],
    },
  },
  {
    id: 5,
    name: 'Field 5',
    data_type: CustomFieldDataType.Monetary,
    extra_data: { default_currency: 'JPY' },
  },
]
const document: Document = {
  id: 1,
  title: 'Doc 1',
  custom_fields: [
    { field: 1, document: 1, created: null, value: 'Text value' },
    { field: 2, document: 1, created: null, value: 'USD100' },
    { field: 3, document: 1, created: null, value: [1, 2, 3] },
  ],
}

describe('CustomFieldDisplayComponent', () => {
  let component: CustomFieldDisplayComponent
  let fixture: ComponentFixture<CustomFieldDisplayComponent>
  let documentService: DocumentService
  let customFieldService: CustomFieldsService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [CustomFieldDisplayComponent],
      imports: [],
      providers: [
        DocumentService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()
  })

  beforeEach(() => {
    documentService = TestBed.inject(DocumentService)
    customFieldService = TestBed.inject(CustomFieldsService)
    jest
      .spyOn(customFieldService, 'listAll')
      .mockReturnValue(of({ results: customFields } as any))
    fixture = TestBed.createComponent(CustomFieldDisplayComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })

  it('should initialize component', () => {
    jest
      .spyOn(documentService, 'getFew')
      .mockReturnValue(of({ results: [] } as any))

    component.fieldDisplayKey = DisplayField.CUSTOM_FIELD + '2'
    expect(component.fieldId).toEqual(2)
    component.document = document
    expect(component.document.title).toEqual('Doc 1')

    expect(component.field).toEqual(customFields[1])
    expect(component.value).toEqual(100)
    expect(component.currency).toEqual('USD')
  })

  it('should get document titles', () => {
    const docLinkDocuments: Document[] = [
      { id: 1, title: 'Document 1' } as any,
      { id: 2, title: 'Document 2' } as any,
      { id: 3, title: 'Document 3' } as any,
    ]
    jest
      .spyOn(documentService, 'getFew')
      .mockReturnValue(of({ results: docLinkDocuments } as any))
    component.fieldId = 3
    component.document = document

    const title1 = component.getDocumentTitle(1)
    const title2 = component.getDocumentTitle(2)
    const title3 = component.getDocumentTitle(3)

    expect(title1).toEqual('Document 1')
    expect(title2).toEqual('Document 2')
    expect(title3).toEqual('Document 3')
  })

  it('should fallback to default currency', () => {
    component['defaultCurrencyCode'] = 'EUR' // mock default locale injection
    component.fieldId = 2
    component.document = {
      id: 1,
      title: 'Doc 1',
      custom_fields: [{ field: 2, document: 1, created: null, value: '100' }],
    }
    expect(component.currency).toEqual('EUR')
    expect(component.value).toEqual(100)
  })

  it('should respect explicit default currency', () => {
    component['defaultCurrencyCode'] = 'EUR' // mock default locale injection
    component.fieldId = 5
    component.document = {
      id: 1,
      title: 'Doc 1',
      custom_fields: [{ field: 5, document: 1, created: null, value: '100' }],
    }
    expect(component.currency).toEqual('JPY')
    expect(component.value).toEqual(100)
  })

  it('should show select value', () => {
    expect(component.getSelectValue(customFields[3], 'ghi-789')).toEqual(
      'Option 3'
    )
  })
})
