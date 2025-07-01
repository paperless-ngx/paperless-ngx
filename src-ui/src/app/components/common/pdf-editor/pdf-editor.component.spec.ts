import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { PDFEditorComponent } from './pdf-editor.component'

describe('PDFEditorComponent', () => {
  let component: PDFEditorComponent
  let fixture: ComponentFixture<PDFEditorComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PDFEditorComponent, NgxBootstrapIconsModule.pick(allIcons)],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        { provide: NgbActiveModal, useValue: {} },
      ],
    }).compileComponents()
    fixture = TestBed.createComponent(PDFEditorComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should rotate and reorder pages', () => {
    component.pages = [
      { page: 1, rotate: 0, splitAfter: false },
      { page: 2, rotate: 0, splitAfter: false },
    ]
    component.rotate(0)
    expect(component.pages[0].rotate).toBe(90)
    component.drop({ previousIndex: 0, currentIndex: 1 } as any)
    expect(component.pages[0].page).toBe(2)
  })
})
