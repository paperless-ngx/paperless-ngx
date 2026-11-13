import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { RunWorkflowConfirmDialogComponent } from './run-workflow-confirm-dialog.component'

describe('RunWorkflowConfirmDialogComponent', () => {
  let component: RunWorkflowConfirmDialogComponent
  let fixture: ComponentFixture<RunWorkflowConfirmDialogComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [NgbActiveModal],
      imports: [RunWorkflowConfirmDialogComponent],
    }).compileComponents()

    fixture = TestBed.createComponent(RunWorkflowConfirmDialogComponent)
    component = fixture.componentInstance
    component.workflows = [{ id: 5, name: 'Manual workflow' } as any]
    fixture.detectChanges()
  })

  it('should disable confirm until a workflow is selected and not force by default', () => {
    expect(component.confirmButtonEnabled).toBeFalsy()
    expect(component.force).toBeFalsy()

    component.workflowId = 5
    component.workflowSelected()
    expect(component.confirmButtonEnabled).toBeTruthy()

    component.workflowId = null
    component.workflowSelected()
    expect(component.confirmButtonEnabled).toBeFalsy()
  })

  it('should render an option per workflow', () => {
    const options = fixture.nativeElement.querySelectorAll(
      '#runWorkflowSelect option'
    )
    // placeholder option + one per workflow
    expect(options).toHaveLength(2)
    expect(options[1].textContent).toContain('Manual workflow')
  })

  it('should describe the checkbox for a selection or a single document', async () => {
    const checkbox = fixture.nativeElement.querySelector('#runWorkflowForce')
    expect(checkbox.checked).toBe(false)
    expect(fixture.nativeElement.textContent).toContain(
      'Run on all selected documents'
    )

    component.singleDocument = true
    component.force = true
    fixture.detectChanges()
    await fixture.whenStable()
    fixture.detectChanges()
    expect(checkbox.checked).toBe(true)
    expect(fixture.nativeElement.textContent).toContain(
      'Run on this document regardless of trigger filters'
    )
    expect(fixture.nativeElement.textContent).not.toContain(
      'Run on all selected documents'
    )
  })
})
