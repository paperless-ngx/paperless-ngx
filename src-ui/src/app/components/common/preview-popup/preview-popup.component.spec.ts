import { ComponentFixture, TestBed } from '@angular/core/testing'

import { PreviewPopupComponent } from './preview-popup.component'
import { PdfViewerComponent } from '../pdf-viewer/pdf-viewer.component'
import { By } from '@angular/platform-browser'
import { SafeUrlPipe } from 'src/app/pipes/safeurl.pipe'

describe('PreviewPopupComponent', () => {
  let component: PreviewPopupComponent
  let fixture: ComponentFixture<PreviewPopupComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [PreviewPopupComponent, PdfViewerComponent, SafeUrlPipe],
    })
    fixture = TestBed.createComponent(PreviewPopupComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should render object if use native PDF viewer', () => {
    component.useNativePdfViewer = true
    component.previewURL = 'sample.pdf'
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('object'))).not.toBeNull()
  })

  it('should render pngx viewer if not use native PDF viewer', () => {
    component.useNativePdfViewer = false
    component.previewURL = 'sample.pdf'
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('object'))).toBeNull()
    expect(fixture.debugElement.query(By.css('pngx-pdf-viewer'))).not.toBeNull()
  })

  it('should render plain text if needed', () => {
    component.renderAsPlainText = true
    component.previewText = 'Hello world'
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('object'))).toBeNull()
    expect(fixture.debugElement.query(By.css('pngx-pdf-viewer'))).toBeNull()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      'Hello world'
    )
  })

  it('should show lock icon on password error', () => {
    component.onError({ name: 'PasswordException' })
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('svg'))).not.toBeNull()
  })

  it('should show message on error', () => {
    component.onError({})
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      'Error loading preview'
    )
  })
})
