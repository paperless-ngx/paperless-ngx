import {
  Component,
  ElementRef,
  EventEmitter,
  Output,
  ViewChild,
  forwardRef,
} from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => FileComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-file',
  templateUrl: './file.component.html',
  styleUrl: './file.component.scss',
})
export class FileComponent extends AbstractInputComponent<string> {
  @Output()
  upload = new EventEmitter<File>()

  public file: File

  @ViewChild('fileInput') fileInput: ElementRef

  get filename(): string {
    return this.value
      ? this.value.substring(this.value.lastIndexOf('/') + 1)
      : null
  }

  onFile(event: Event) {
    this.file = (event.target as HTMLInputElement).files[0]
  }

  uploadClicked() {
    this.upload.emit(this.file)
    this.clear()
  }

  clear() {
    this.file = undefined
    this.fileInput.nativeElement.value = null
    this.writeValue(null)
    this.onChange(null)
  }
}
