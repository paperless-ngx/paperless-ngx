import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import { DocumentService } from 'src/app/services/rest/document.service'
import { MergeConfirmDialogComponent } from './merge-confirm-dialog.component'

describe('MergeConfirmDialogComponent', () => {
  let component: MergeConfirmDialogComponent
  let fixture: ComponentFixture<MergeConfirmDialogComponent>
  let documentService: DocumentService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [MergeConfirmDialogComponent],
      imports: [
        NgxBootstrapIconsModule.pick(allIcons),
        ReactiveFormsModule,
        FormsModule,
      ],
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(MergeConfirmDialogComponent)
    documentService = TestBed.inject(DocumentService)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should fetch documents on ngOnInit', () => {
    const documents = [
      { id: 1, name: 'Document 1' },
      { id: 2, name: 'Document 2' },
      { id: 3, name: 'Document 3' },
    ]
    jest.spyOn(documentService, 'getFew').mockReturnValue(
      of({
        all: documents.map((d) => d.id),
        count: documents.length,
        results: documents,
      })
    )

    component.ngOnInit()

    expect(component.documents).toEqual(documents)
    expect(documentService.getFew).toHaveBeenCalledWith(component.documentIDs)
  })

  it('should move documentIDs on drop', () => {
    component.documentIDs = [1, 2, 3]
    const event = {
      previousIndex: 1,
      currentIndex: 2,
    }

    component.onDrop(event as any)

    expect(component.documentIDs).toEqual([1, 3, 2])
  })

  it('should get document by ID', () => {
    const documents = [
      { id: 1, name: 'Document 1' },
      { id: 2, name: 'Document 2' },
      { id: 3, name: 'Document 3' },
    ]
    jest.spyOn(documentService, 'getFew').mockReturnValue(
      of({
        all: documents.map((d) => d.id),
        count: documents.length,
        results: documents,
      })
    )

    component.ngOnInit()

    expect(component.getDocument(2)).toEqual({ id: 2, name: 'Document 2' })
  })
})
