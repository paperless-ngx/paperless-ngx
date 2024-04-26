import { ComponentFixture, TestBed } from '@angular/core/testing'
import { of } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { DocumentService } from 'src/app/services/rest/document.service'
import { CustomFieldDisplayComponent } from './custom-field-display.component'
import { DisplayField, Document } from 'src/app/data/document'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'

const customFields: CustomField[] = [
  { id: 1, name: 'Field 1', data_type: CustomFieldDataType.String },
  { id: 2, name: 'Field 2', data_type: CustomFieldDataType.Monetary },
  { id: 3, name: 'Field 3', data_type: CustomFieldDataType.DocumentLink },
]
const document: Document = {
  id: 1,
  title: 'Doc 1',
  custom_fields: [
    { field: 1, document: 1, created: null, value: 'Text value' },
    { field: 2, document: 1, created: null, value: '100 USD' },
    { field: 3, document: 1, created: null, value: '1,2,3' },
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
      providers: [DocumentService],
      imports: [HttpClientTestingModule],
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
})
