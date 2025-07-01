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

  it('should rotate, delete and reorder pages', () => {
    component.pages = [
      { page: 1, rotate: 0, splitAfter: false, selected: false },
      { page: 2, rotate: 0, splitAfter: false, selected: false },
    ]
    component.toggleSelection(0)
    component.rotateSelected(90)
    expect(component.pages[0].rotate).toBe(90)
    component.toggleSelection(0) // deselect
    component.toggleSelection(1)
    component.deleteSelected()
    expect(component.pages.length).toBe(1)
    component.pages.push({ page: 2, rotate: 0, splitAfter: false })
    component.drop({ previousIndex: 0, currentIndex: 1 } as any)
    expect(component.pages[0].page).toBe(2)
    component.rotate(0)
    expect(component.pages[0].rotate).toBe(90)
  })
})
