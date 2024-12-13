import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { PdfViewerComponent } from 'ng2-pdf-viewer'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { DeletePagesConfirmDialogComponent } from './delete-pages-confirm-dialog.component'

describe('DeletePagesConfirmDialogComponent', () => {
  let component: DeletePagesConfirmDialogComponent
  let fixture: ComponentFixture<DeletePagesConfirmDialogComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [DeletePagesConfirmDialogComponent, PdfViewerComponent],
      imports: [
        NgxBootstrapIconsModule.pick(allIcons),
        FormsModule,
        ReactiveFormsModule,
      ],
      providers: [
        NgbActiveModal,
        SafeHtmlPipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()
    fixture = TestBed.createComponent(DeletePagesConfirmDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should return a string with comma-separated pages', () => {
    component.pages = [1, 2, 3, 4]
    expect(component.pagesString).toEqual('1, 2, 3, 4')
  })

  it('should update totalPages when pdf is loaded', () => {
    component.pdfPreviewLoaded({ numPages: 5 } as any)
    expect(component.totalPages).toEqual(5)
  })

  it('should update checks when page is rendered', () => {
    const event = {
      target: document.createElement('div'),
      detail: { pageNumber: 1 },
    } as any
    component.pageRendered(event)
    expect(component['checks'].length).toEqual(1)
  })

  it('should update pages when page check is changed', () => {
    component.pageCheckChanged(1)
    expect(component.pages).toEqual([1])
    component.pageCheckChanged(1)
    expect(component.pages).toEqual([])
  })
})
