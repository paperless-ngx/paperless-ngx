import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DocumentService } from 'src/app/services/rest/document.service'
import { AddExistingDocumentVersionDialogComponent } from './add-existing-document-version-dialog.component'

describe('AddExistingDocumentVersionDialogComponent', () => {
  let component: AddExistingDocumentVersionDialogComponent
  let fixture: ComponentFixture<AddExistingDocumentVersionDialogComponent>
  let activeModal: jest.Mocked<Pick<NgbActiveModal, 'dismiss'>>

  beforeEach(async () => {
    activeModal = { dismiss: jest.fn() }
    await TestBed.configureTestingModule({
      imports: [AddExistingDocumentVersionDialogComponent],
      providers: [
        {
          provide: NgbActiveModal,
          useValue: activeModal,
        },
        {
          provide: DocumentService,
          useValue: {},
        },
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(AddExistingDocumentVersionDialogComponent)
    component = fixture.componentInstance
    component.rootDocumentID = 3
    fixture.detectChanges()
  })

  it('should emit the single selected document', () => {
    const emitSpy = jest.spyOn(component.confirmClicked, 'emit')
    component.selectedDocumentIDs = [20]

    component.confirm()

    expect(emitSpy).toHaveBeenCalledWith(20)
  })

  it('should require exactly one selected document', () => {
    const emitSpy = jest.spyOn(component.confirmClicked, 'emit')
    component.selectedDocumentIDs = [20, 21]

    component.confirm()

    expect(emitSpy).not.toHaveBeenCalled()
  })

  it('should dismiss on cancel', () => {
    component.cancel()

    expect(activeModal.dismiss).toHaveBeenCalled()
  })

  it('should re-render the buttons when they are toggled from outside', async () => {
    const cancelButton: HTMLButtonElement = fixture.nativeElement.querySelector(
      '.modal-footer button'
    )
    expect(cancelButton.disabled).toBeFalsy()

    // No detectChanges: the dropdown toggling this from a request callback is
    // all that happens, and nothing else schedules a render for the modal
    component.buttonsEnabled.set(false)
    await fixture.whenStable()
    expect(cancelButton.disabled).toBeTruthy()

    component.buttonsEnabled.set(true)
    await fixture.whenStable()
    expect(cancelButton.disabled).toBeFalsy()
  })
})
