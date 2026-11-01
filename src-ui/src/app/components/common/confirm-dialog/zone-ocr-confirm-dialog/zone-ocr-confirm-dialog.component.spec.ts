import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { of } from 'rxjs'
import { MATCH_NONE } from 'src/app/data/matching-model'
import { OcrTemplate } from 'src/app/data/ocr-template'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { ZoneOcrConfirmDialogComponent } from './zone-ocr-confirm-dialog.component'

const templates: OcrTemplate[] = [
  {
    id: 1,
    name: 'Invoices',
    match: '',
    matching_algorithm: MATCH_NONE,
    sample_document: null,
    source_width: 0,
    source_height: 0,
    enabled: true,
    zones: [],
  },
]

describe('ZoneOcrConfirmDialogComponent', () => {
  let component: ZoneOcrConfirmDialogComponent
  let fixture: ComponentFixture<ZoneOcrConfirmDialogComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
      imports: [ZoneOcrConfirmDialogComponent],
    })
    jest
      .spyOn(TestBed.inject(OcrTemplateService), 'listAll')
      .mockReturnValue(of({ count: 1, all: [1], results: templates }))

    fixture = TestBed.createComponent(ZoneOcrConfirmDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should offer templates and default to all matching templates', () => {
    expect(component.templates()).toEqual(templates)
    expect(component.template).toBeNull()
    expect(fixture.nativeElement.textContent).toContain('OCR template')
  })
})
