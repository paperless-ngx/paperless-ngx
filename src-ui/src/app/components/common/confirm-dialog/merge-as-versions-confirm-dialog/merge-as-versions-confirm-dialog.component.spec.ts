import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import { DocumentService } from 'src/app/services/rest/document.service'
import { MergeAsVersionsConfirmDialogComponent } from './merge-as-versions-confirm-dialog.component'

describe('MergeAsVersionsConfirmDialogComponent', () => {
  let component: MergeAsVersionsConfirmDialogComponent
  let fixture: ComponentFixture<MergeAsVersionsConfirmDialogComponent>
  let documentService: DocumentService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        NgxBootstrapIconsModule.pick(allIcons),
        MergeAsVersionsConfirmDialogComponent,
      ],
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(MergeAsVersionsConfirmDialogComponent)
    documentService = TestBed.inject(DocumentService)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should fetch selected documents', () => {
    const documents = [
      { id: 1, title: 'Document 1' },
      { id: 2, title: 'Document 2' },
    ]
    jest.spyOn(documentService, 'getFew').mockReturnValue(
      of({
        all: [1, 2],
        count: 2,
        results: documents,
      })
    )
    component.documentIDs.set([1, 2])

    component.ngOnInit()

    expect(component.documents()).toEqual(documents)
    expect(documentService.getFew).toHaveBeenCalledWith([1, 2])
  })

  it('should exclude the root from the draggable documents', () => {
    component.documentIDs.set([1, 2, 3])
    component.rootDocumentID.set(2)

    expect(component.versionDocumentIDs()).toEqual([1, 3])
  })

  it('should move draggable documents while keeping the root fixed', () => {
    component.documentIDs.set([1, 2, 3])
    component.rootDocumentID.set(1)

    component.onDrop({ previousIndex: 1, currentIndex: 0 } as any)

    expect(component.documentIDs()).toEqual([1, 3, 2])
    expect(component.versionDocumentIDs()).toEqual([3, 2])
  })
})
