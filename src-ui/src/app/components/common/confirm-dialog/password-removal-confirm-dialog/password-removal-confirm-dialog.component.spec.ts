import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { PasswordRemovalConfirmDialogComponent } from './password-removal-confirm-dialog.component'

describe('PasswordRemovalConfirmDialogComponent', () => {
  let component: PasswordRemovalConfirmDialogComponent
  let fixture: ComponentFixture<PasswordRemovalConfirmDialogComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      providers: [NgbActiveModal],
      imports: [
        NgxBootstrapIconsModule.pick(allIcons),
        PasswordRemovalConfirmDialogComponent,
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(PasswordRemovalConfirmDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should default to replacing the document', () => {
    expect(component.updateDocument).toBe(true)
    expect(
      fixture.debugElement.query(By.css('#removeReplace')).nativeElement.checked
    ).toBe(true)
  })

  it('should allow creating a new document with metadata and delete toggle', () => {
    component.onUpdateDocumentChange(false)
    fixture.detectChanges()

    expect(component.updateDocument).toBe(false)
    expect(fixture.debugElement.query(By.css('#copyMetaRemove'))).not.toBeNull()

    component.includeMetadata = false
    component.deleteOriginal = true
    component.onUpdateDocumentChange(true)
    expect(component.updateDocument).toBe(true)
    expect(component.includeMetadata).toBe(true)
    expect(component.deleteOriginal).toBe(false)
  })

  it('should emit confirm when confirmed', () => {
    let confirmed = false
    component.confirmClicked.subscribe(() => (confirmed = true))
    component.confirm()
    expect(confirmed).toBe(true)
  })
})
