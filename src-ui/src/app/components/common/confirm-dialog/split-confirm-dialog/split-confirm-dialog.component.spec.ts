import { ComponentFixture, TestBed } from '@angular/core/testing'

import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { PdfViewerModule } from 'ng2-pdf-viewer'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SplitConfirmDialogComponent } from './split-confirm-dialog.component'

describe('SplitConfirmDialogComponent', () => {
  let component: SplitConfirmDialogComponent
  let fixture: ComponentFixture<SplitConfirmDialogComponent>
  let documentService: DocumentService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [SplitConfirmDialogComponent],
      imports: [
        NgxBootstrapIconsModule.pick(allIcons),
        ReactiveFormsModule,
        FormsModule,
        PdfViewerModule,
      ],
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(SplitConfirmDialogComponent)
    documentService = TestBed.inject(DocumentService)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should load document on init', () => {
    const getSpy = jest.spyOn(documentService, 'get')
    component.documentID = 1
    getSpy.mockReturnValue(of({ id: 1 } as any))
    component.ngOnInit()
    expect(documentService.get).toHaveBeenCalledWith(1)
  })

  it('should update pagesString when pages are added', () => {
    component.totalPages = 5
    component.page = 2
    component.addSplit()
    expect(component.pagesString).toEqual('1-2,3-5')
    component.page = 4
    component.addSplit()
    expect(component.pagesString).toEqual('1-2,3-4,5')
  })

  it('should update pagesString when pages are removed', () => {
    component.totalPages = 5
    component.page = 2
    component.addSplit()
    component.page = 4
    component.addSplit()
    expect(component.pagesString).toEqual('1-2,3-4,5')
    component.removeSplit(0)
    expect(component.pagesString).toEqual('1-4,5')
  })

  it('should enable confirm button when pages are added', () => {
    component.totalPages = 5
    component.page = 2
    component.addSplit()
    expect(component.confirmButtonEnabled).toBeTruthy()
  })

  it('should disable confirm button when all pages are removed', () => {
    component.totalPages = 5
    component.page = 2
    component.addSplit()
    component.removeSplit(0)
    expect(component.confirmButtonEnabled).toBeFalsy()
  })

  it('should not add split if page is the last page', () => {
    component.totalPages = 5
    component.page = 5
    component.addSplit()
    expect(component.pagesString).toEqual('1-5')
  })

  it('should update totalPages when pdf is loaded', () => {
    component.pdfPreviewLoaded({ numPages: 5 } as any)
    expect(component.totalPages).toEqual(5)
  })

  it('should correctly disable split button', () => {
    component.totalPages = 5
    component.page = 1
    expect(component.canSplit).toBeTruthy()
    component.page = 5
    expect(component.canSplit).toBeFalsy()
    component.page = 4
    expect(component.canSplit).toBeTruthy()
    component['pages'] = new Set([1, 2, 3, 4])
    expect(component.canSplit).toBeFalsy()
  })
})
