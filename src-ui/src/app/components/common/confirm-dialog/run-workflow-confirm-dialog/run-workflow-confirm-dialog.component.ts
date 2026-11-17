import { Component } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { Workflow } from 'src/app/data/workflow'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-run-workflow-confirm-dialog',
  templateUrl: './run-workflow-confirm-dialog.component.html',
  imports: [FormsModule],
})
export class RunWorkflowConfirmDialogComponent extends ConfirmDialogComponent {
  public workflows: Workflow[] = []

  public workflowId: number = null

  public singleDocument: boolean = false

  // i.e. ignore the workflow's trigger filters
  public force: boolean = false

  override confirmButtonEnabled = false

  public workflowSelected(): void {
    this.confirmButtonEnabled = !!this.workflowId
  }
}
