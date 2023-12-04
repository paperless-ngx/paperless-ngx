import { HttpClientTestingModule } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgSelectModule } from '@ng-select/ng-select'
import { of, throwError } from 'rxjs'
import { DocumentService } from 'src/app/services/rest/document.service'
import { DocumentLinkComponent } from './document-link.component'
import { FILTER_TITLE } from 'src/app/data/filter-rule-type'

const documents = [
  {
    id: 1,
    title: 'Document 1 foo',
  },
  {
    id: 12,
    title: 'Document 12 bar',
  },
  {
    id: 23,
    title: 'Document 23 bar',
  },
]

describe('DocumentLinkComponent', () => {
  let component: DocumentLinkComponent
  let fixture: ComponentFixture<DocumentLinkComponent>
  let documentService: DocumentService

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [DocumentLinkComponent],
      imports: [
        HttpClientTestingModule,
        NgSelectModule,
        FormsModule,
        ReactiveFormsModule,
      ],
    })
    documentService = TestBed.inject(DocumentService)
    fixture = TestBed.createComponent(DocumentLinkComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should retrieve selected documents from APIs', () => {
    const getSpy = jest.spyOn(documentService, 'getCachedMany')
    getSpy.mockImplementation((ids) => {
      return of(documents.filter((d) => ids.includes(d.id)))
    })
    component.writeValue([1])
    expect(getSpy).toHaveBeenCalled()
  })

  it('should search API on select text input', () => {
    const listSpy = jest.spyOn(documentService, 'listFiltered')
    listSpy.mockImplementation(
      (page, pageSize, sortField, sortReverse, filterRules, extraParams) => {
        const docs = documents.filter((d) =>
          d.title.includes(filterRules[0].value)
        )
        return of({
          count: docs.length,
          results: docs,
          all: docs.map((d) => d.id),
        })
      }
    )
    component.documentsInput$.next('bar')
    expect(listSpy).toHaveBeenCalledWith(
      1,
      null,
      'created',
      true,
      [{ rule_type: FILTER_TITLE, value: 'bar' }],
      { truncate_content: true }
    )
    listSpy.mockReturnValueOnce(throwError(() => new Error()))
    component.documentsInput$.next('foo')
  })

  it('should support unselect', () => {
    const getSpy = jest.spyOn(documentService, 'getCachedMany')
    getSpy.mockImplementation((ids) => {
      return of(documents.filter((d) => ids.includes(d.id)))
    })
    component.writeValue([12, 23])
    component.unselect({ id: 23 })
    fixture.detectChanges()
    expect(component.selectedDocuments).toEqual([documents[1]])
  })

  it('should use correct compare, trackBy functions', () => {
    expect(component.compareDocuments(documents[0], { id: 1 })).toBeTruthy()
    expect(component.compareDocuments(documents[0], { id: 2 })).toBeFalsy()
    expect(component.trackByFn(documents[1])).toEqual(12)
  })
})
