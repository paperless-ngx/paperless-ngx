import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { provideRouter } from '@angular/router'
import { NgSelectComponent } from '@ng-select/ng-select'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { of, Subject, throwError } from 'rxjs'
import { FILTER_SIMPLE_TITLE } from 'src/app/data/filter-rule-type'
import { DocumentService } from 'src/app/services/rest/document.service'
import { DocumentLinkComponent } from './document-link.component'

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
    id: 16,
    title: 'Document 16 bar',
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
      imports: [DocumentLinkComponent, NgxBootstrapIconsModule.pick(allIcons)],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    })
    documentService = TestBed.inject(DocumentService)
    fixture = TestBed.createComponent(DocumentLinkComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should retrieve selected documents from API', () => {
    const getSpy = jest.spyOn(documentService, 'getFew')
    getSpy.mockImplementation((ids) => {
      const docs = documents.filter((d) => ids.includes(d.id))
      return of({
        count: docs.length,
        all: docs.map((d) => d.id),
        results: docs,
      })
    })
    component.writeValue([1])
    expect(getSpy).toHaveBeenCalled()
  })

  it('should render loading and selected documents after async updates', async () => {
    const result$ = new Subject<any>()
    jest.spyOn(documentService, 'getFew').mockReturnValue(result$)

    component.writeValue([1])
    await fixture.whenStable()

    const select = fixture.debugElement.query(By.directive(NgSelectComponent))
      .componentInstance as NgSelectComponent
    expect(select.loading()).toBe(true)

    result$.next({ count: 1, all: [1], results: [documents[0]] })
    result$.complete()
    await fixture.whenStable()

    expect(select.loading()).toBe(false)
    expect(fixture.nativeElement.textContent).toContain(documents[0].title)
  })

  it('shoud maintain ordering of selected documents', () => {
    const getSpy = jest.spyOn(documentService, 'getFew')
    getSpy.mockImplementation((ids) => {
      const docs = documents.filter((d) => ids.includes(d.id))
      return of({
        count: docs.length,
        all: docs.map((d) => d.id),
        results: docs,
      })
    })
    component.writeValue([12, 1])
    expect(component.selectedDocuments).toEqual([documents[1], documents[0]])
  })

  it('should retrieve document IDs from selected documents', () => {
    component.selectedDocuments = documents
    expect(component.selectedDocumentIDs).toEqual([1, 12, 16, 23])
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
      [{ rule_type: FILTER_SIMPLE_TITLE, value: 'bar' }],
      { truncate_content: true }
    )
    listSpy.mockReturnValueOnce(throwError(() => new Error()))
    component.documentsInput$.next('foo')
  })

  it('should load values correctly', () => {
    const getSpy = jest.spyOn(documentService, 'getFew')
    getSpy.mockImplementation((ids) => {
      const docs = documents.filter((d) => ids.includes(d.id))
      return of({
        count: docs.length,
        all: docs.map((d) => d.id),
        results: docs,
      })
    })
    component.writeValue([12, 23])
    expect(component.value).toEqual([12, 23])
    expect(component.selectedDocuments).toEqual([documents[1], documents[3]])
    component.writeValue(null)
    expect(component.value).toEqual([])
    expect(component.selectedDocuments).toEqual([])
    component.writeValue([])
    expect(component.value).toEqual([])
    expect(component.selectedDocuments).toEqual([])
  })

  it('should preserve and neutrally label unavailable document IDs', async () => {
    jest.spyOn(documentService, 'getFew').mockReturnValue(
      of({
        count: 0,
        all: [],
        results: [],
      })
    )

    component.writeValue([99])
    await fixture.whenStable()

    expect(component.selectedDocuments).toEqual([{ id: 99 }])
    expect(fixture.nativeElement.textContent).toContain('Unavailable')
    expect(fixture.nativeElement.textContent).not.toContain('Not found')
  })

  it('should support unselect', () => {
    const getSpy = jest.spyOn(documentService, 'getFew')
    getSpy.mockImplementation((ids) => {
      const docs = documents.filter((d) => ids.includes(d.id))
      return of({
        count: docs.length,
        all: docs.map((d) => d.id),
        results: docs,
      })
    })
    component.writeValue([12, 23])
    component.unselect({ id: 23 })
    fixture.detectChanges()
    expect(component.selectedDocuments).toEqual([documents[1]])
  })

  it('should not unselect documents when disabled', () => {
    component.disabled = true
    component.selectedDocuments = [documents[0]]

    component.unselect(documents[0])

    expect(component.selectedDocuments).toEqual([documents[0]])
  })

  it('should use correct compare, trackBy functions', () => {
    expect(component.compareDocuments(documents[0], { id: 1 })).toBeTruthy()
    expect(component.compareDocuments(documents[0], { id: 2 })).toBeFalsy()
    expect(component.trackByFn(documents[1])).toEqual(12)
  })

  it('should not include the current document or already selected documents in results', () => {
    let foundDocs
    component.foundDocuments$.subscribe((found) => (foundDocs = found))
    component.parentDocumentID = 23
    component.selectedDocuments = [documents[2]]
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
    expect(foundDocs).toEqual([documents[1]])
  })
})
