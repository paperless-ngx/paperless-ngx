import { NgTemplateOutlet } from '@angular/common'
import {
  Component,
  EventEmitter,
  HostListener,
  Input,
  Output,
} from '@angular/core'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Folder } from 'src/app/data/folder'

@Component({
  selector: 'pngx-folder-filter-dropdown',
  templateUrl: './folder-filter-dropdown.component.html',
  styleUrls: ['./folder-filter-dropdown.component.scss'],
  imports: [NgbDropdownModule, NgxBootstrapIconsModule, NgTemplateOutlet],
})
export class FolderFilterDropdownComponent {
  /** Full flat list of all folders (from ?parent=all) */
  @Input() folders: Folder[] = []

  /** Currently active folder ID (null = no filter) */
  @Input() selectedId: number | null = null

  /** Whether the component is disabled */
  @Input() disabled = false

  /** Emits the selected folder ID, or null to clear the filter */
  @Output() folderSelected = new EventEmitter<number | null>()

  expandedIds = new Set<number>()

  get rootFolders(): Folder[] {
    return this.folders.filter((f) => !f.parent)
  }

  childrenOf(parentId: number): Folder[] {
    return this.folders.filter((f) => f.parent === parentId)
  }

  hasChildren(folder: Folder): boolean {
    return this.folders.some((f) => f.parent === folder.id)
  }

  isExpanded(id: number): boolean {
    return this.expandedIds.has(id)
  }

  toggleExpand(id: number, event: Event): void {
    event.stopPropagation()
    if (this.expandedIds.has(id)) {
      this.expandedIds.delete(id)
    } else {
      this.expandedIds.add(id)
    }
  }

  get selectedName(): string {
    if (this.selectedId == null) return $localize`Folder`
    return this.folders.find((f) => f.id === this.selectedId)?.name ?? $localize`Folder`
  }

  get isActive(): boolean {
    return this.selectedId != null
  }

  selectFolder(id: number, dropdown: any): void {
    if (this.selectedId === id) {
      // clicking the already-selected folder clears the filter
      this.folderSelected.emit(null)
    } else {
      this.folderSelected.emit(id)
    }
    dropdown.close()
  }

  clearFilter(dropdown: any, event: Event): void {
    event.stopPropagation()
    this.folderSelected.emit(null)
    dropdown.close()
  }
}
