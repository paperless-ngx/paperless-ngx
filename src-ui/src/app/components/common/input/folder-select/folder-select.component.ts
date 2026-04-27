import { NgTemplateOutlet } from '@angular/common'
import {
  Component,
  EventEmitter,
  forwardRef,
  Input,
  OnInit,
  Output,
} from '@angular/core'
import { FormsModule, NG_VALUE_ACCESSOR } from '@angular/forms'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Folder } from 'src/app/data/folder'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  selector: 'pngx-input-folder-select',
  templateUrl: './folder-select.component.html',
  styleUrls: ['./folder-select.component.scss'],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => FolderSelectComponent),
      multi: true,
    },
  ],
  imports: [NgbDropdownModule, NgxBootstrapIconsModule, NgTemplateOutlet, FormsModule],
})
export class FolderSelectComponent
  extends AbstractInputComponent<number>
  implements OnInit
{
  @Input() folders: Folder[] = []
  @Input() allowNull = true

  /** Emits a name string when the user wants to create a new folder */
  @Output() createNew = new EventEmitter<string>()

  expandedIds = new Set<number>()
  creatingNew = false
  newFolderName = ''

  override ngOnInit(): void {
    super.ngOnInit()
  }

  get rootFolders(): Folder[] {
    return this.folders.filter((f) => !f.parent)
  }

  childrenOf(parentId: number): Folder[] {
    return this.folders.filter((f) => f.parent === parentId)
  }

  hasChildren(folder: Folder): boolean {
    return this.folders.some((f) => f.parent === folder.id)
  }

  get selectedName(): string {
    if (this.value == null) return $localize`None`
    return this.folders.find((f) => f.id === this.value)?.name ?? $localize`None`
  }

  toggleExpand(folderId: number, event: Event): void {
    event.stopPropagation()
    if (this.expandedIds.has(folderId)) {
      this.expandedIds.delete(folderId)
    } else {
      this.expandedIds.add(folderId)
    }
  }

  isExpanded(folderId: number): boolean {
    return this.expandedIds.has(folderId)
  }

  selectFolder(id: number | null, dropdown: any): void {
    this.value = id
    this.onChange(id)
    this.onTouched()
    dropdown.close()
  }

  startCreating(event: Event): void {
    event.stopPropagation()
    this.creatingNew = true
    this.newFolderName = ''
  }

  confirmCreate(event: Event, dropdown: any): void {
    event.stopPropagation()
    const name = this.newFolderName?.trim()
    if (name) {
      this.createNew.emit(name)
    }
    this.creatingNew = false
    this.newFolderName = ''
    dropdown.close()
  }

  cancelCreate(event: Event): void {
    event.stopPropagation()
    this.creatingNew = false
    this.newFolderName = ''
  }
}
