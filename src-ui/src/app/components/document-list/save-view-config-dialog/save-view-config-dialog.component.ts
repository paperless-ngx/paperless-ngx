import {
  Component,
  EventEmitter,
  Input,
  OnInit,
  Output,
  inject,
} from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { CheckComponent } from '../../common/input/check/check.component'
import { TextComponent } from '../../common/input/text/text.component'

@Component({
  selector: 'pngx-save-view-config-dialog',
  templateUrl: './save-view-config-dialog.component.html',
  styleUrls: ['./save-view-config-dialog.component.scss'],
  imports: [CheckComponent, TextComponent, FormsModule, ReactiveFormsModule],
})
export class SaveViewConfigDialogComponent implements OnInit {
  private modal = inject(NgbActiveModal)

  @Output()
  public saveClicked = new EventEmitter()

  @Input()
  error

  @Input()
  buttonsEnabled = true

  closeEnabled = false

  _defaultName = ''

  get defaultName() {
    return this._defaultName
  }

  @Input()
  set defaultName(value: string) {
    this._defaultName = value
    this.saveViewConfigForm.patchValue({ name: value })
  }

  saveViewConfigForm = new FormGroup({
    name: new FormControl(''),
    showInSideBar: new FormControl(false),
    showOnDashboard: new FormControl(false),
  })

  ngOnInit(): void {
    // wait to enable close button so it doesn't steal focus from input since its the first clickable element in the DOM
    setTimeout(() => {
      this.closeEnabled = true
    })
  }

  save() {
    this.saveClicked.emit(this.saveViewConfigForm.value)
  }

  cancel() {
    this.modal.close()
  }
}
