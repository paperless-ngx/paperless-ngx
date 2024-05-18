import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { SelectComponent } from '../input/select/select.component'
import { SelectDialogComponent } from './select-dialog.component'

describe('SelectDialogComponent', () => {
  let component: SelectDialogComponent
  let fixture: ComponentFixture<SelectDialogComponent>
  let modal: NgbActiveModal

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [SelectDialogComponent, SelectComponent],
      providers: [NgbActiveModal],
      imports: [NgSelectModule, FormsModule, ReactiveFormsModule],
    }).compileComponents()

    modal = TestBed.inject(NgbActiveModal)
    fixture = TestBed.createComponent(SelectDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should close modal on cancel', () => {
    const closeSpy = jest.spyOn(modal, 'close')
    component.cancelClicked()
    expect(closeSpy).toHaveBeenCalled()
  })
})
