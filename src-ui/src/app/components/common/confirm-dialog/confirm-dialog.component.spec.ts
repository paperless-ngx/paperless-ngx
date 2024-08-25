import {
  ComponentFixture,
  TestBed,
  discardPeriodicTasks,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { ConfirmDialogComponent } from './confirm-dialog.component'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { Subject } from 'rxjs'

describe('ConfirmDialogComponent', () => {
  let component: ConfirmDialogComponent
  let modal: NgbActiveModal
  let fixture: ComponentFixture<ConfirmDialogComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [ConfirmDialogComponent, SafeHtmlPipe],
      providers: [NgbActiveModal, SafeHtmlPipe],
      imports: [],
    }).compileComponents()

    modal = TestBed.inject(NgbActiveModal)

    fixture = TestBed.createComponent(ConfirmDialogComponent)
    component = fixture.componentInstance
    component.title = 'Confirm delete'
    component.messageBold = 'Do you really want to delete document file.pdf?'
    component.message =
      'The files for this document will be deleted permanently. This operation cannot be undone.'
    component.btnClass = 'btn-danger'
    component.btnCaption = 'Delete document'

    fixture.detectChanges()
  })

  it('should support alternative', () => {
    let alternativeClickedResult
    let alternativeSubjectResult
    component.alternativeClicked.subscribe((result) => {
      alternativeClickedResult = true
    })
    component.alternative()
    // with subject
    const subject = new Subject<boolean>()
    component.alternativeSubject = subject
    subject.asObservable().subscribe((result) => {
      alternativeSubjectResult = result
    })
    component.alternative()
    expect(alternativeClickedResult).toBeTruthy()
    expect(alternativeSubjectResult).toBeTruthy()
  })

  it('should support confirm', () => {
    let confirmClickedResult
    let confirmSubjectResult
    component.confirmClicked.subscribe((result) => {
      confirmClickedResult = true
    })
    component.confirm()
    // with subject
    const subject = new Subject<boolean>()
    component.confirmSubject = subject
    subject.asObservable().subscribe((result) => {
      confirmSubjectResult = result
    })
    component.confirm()
    expect(confirmClickedResult).toBeTruthy()
    expect(confirmSubjectResult).toBeTruthy()
  })

  it('should support cancel & close modal', () => {
    let confirmSubjectResult
    const closeModalSpy = jest.spyOn(modal, 'close')
    component.cancel()
    const subject = new Subject<boolean>()
    component.confirmSubject = subject
    subject.asObservable().subscribe((result) => {
      confirmSubjectResult = result
    })
    component.cancel()
    // with subject
    expect(closeModalSpy).toHaveBeenCalled()
    expect(confirmSubjectResult).toBeFalsy()
  })
})
