import { NgTemplateOutlet } from '@angular/common'
import {
  Component,
  HostListener,
  inject,
  OnInit,
} from '@angular/core'
import { FormsModule } from '@angular/forms'
import { Router } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Folder } from 'src/app/data/folder'
import { FilterRule } from 'src/app/data/filter-rule'
import { FILTER_FOLDER } from 'src/app/data/filter-rule-type'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FolderService } from 'src/app/services/rest/folder.service'
import { ToastService } from 'src/app/services/toast.service'
import { PermissionsDialogComponent } from '../common/permissions-dialog/permissions-dialog.component'

@Component({
  selector: 'pngx-folder-tree',
  templateUrl: './folder-tree.component.html',
  styleUrls: ['./folder-tree.component.scss'],
  imports: [FormsModule, NgTemplateOutlet, NgxBootstrapIconsModule],
})
export class FolderTreeComponent implements OnInit {
  private folderService = inject(FolderService)
  private documentListViewService = inject(DocumentListViewService)
  private router = inject(Router)
  private toastService = inject(ToastService)
  private modalService = inject(NgbModal)

  folders: Folder[] = []
  activeFolderId: number | null = null

  // inline edit state
  editingFolderId: number | null = null
  editingName: string = ''

  // inline create state
  creatingRoot: boolean = false
  creatingChildOf: number | null = null
  newFolderName: string = ''

  // right-click context menu
  contextMenu: { x: number; y: number; folder: Folder | null } | null = null

  ngOnInit(): void {
    this.loadFolders()
  }

  loadFolders(): void {
    this.folderService.listAll(null, null, { parent: 'all' }).subscribe({
      next: (r) => (this.folders = r.results),
      error: () =>
        this.toastService.showError($localize`Could not load folders`),
    })
  }

  get rootFolders(): Folder[] {
    return this.folders.filter((f) => f.parent == null)
  }

  childrenOf(parentId: number): Folder[] {
    return this.folders.filter((f) => f.parent === parentId)
  }

  selectFolder(folder: Folder): void {
    this.activeFolderId = folder.id
    const rules: FilterRule[] = [
      { rule_type: FILTER_FOLDER, value: folder.id.toString() },
    ]
    this.documentListViewService.quickFilter(rules)
  }

  // ---- Right-click context menu ----

  onRightClick(event: MouseEvent, folder: Folder | null): void {
    event.preventDefault()
    event.stopPropagation()
    this.contextMenu = { x: event.clientX, y: event.clientY, folder }
  }

  @HostListener('document:click')
  closeContextMenu(): void {
    this.contextMenu = null
  }

  // ---- Create ----

  startCreatingRoot(): void {
    this.creatingChildOf = null
    this.creatingRoot = true
    this.newFolderName = ''
  }

  startCreatingChild(folder: Folder | null): void {
    this.creatingRoot = false
    this.creatingChildOf = folder ? folder.id : null
    if (!folder) {
      this.creatingRoot = true
    }
    this.newFolderName = ''
  }

  cancelCreate(): void {
    this.creatingRoot = false
    this.creatingChildOf = null
    this.newFolderName = ''
  }

  createFolder(name: string, parentId: number | null): void {
    if (!name?.trim()) return
    const payload: Partial<Folder> = { name: name.trim() }
    if (parentId != null) payload.parent = parentId
    this.folderService.create(payload as Folder).subscribe({
      next: () => {
        this.cancelCreate()
        this.loadFolders()
      },
      error: () =>
        this.toastService.showError($localize`Could not create folder`),
    })
  }

  // ---- Rename ----

  startEdit(folder: Folder): void {
    this.editingFolderId = folder.id
    this.editingName = folder.name
  }

  cancelEdit(): void {
    this.editingFolderId = null
    this.editingName = ''
  }

  renameFolder(folder: Folder, newName: string): void {
    if (!newName?.trim()) return
    this.folderService.patch({ ...folder, name: newName.trim() }).subscribe({
      next: () => {
        this.cancelEdit()
        this.loadFolders()
      },
      error: () =>
        this.toastService.showError($localize`Could not rename folder`),
    })
  }

  // ---- Delete ----

  deleteFolder(folder: Folder): void {
    if (
      !confirm(
        $localize`Delete folder "${folder.name}" and all its sub-folders?`
      )
    )
      return
    this.folderService.delete(folder).subscribe({
      next: () => {
        if (this.activeFolderId === folder.id) {
          this.activeFolderId = null
        }
        this.loadFolders()
      },
      error: () =>
        this.toastService.showError($localize`Could not delete folder`),
    })
  }

  // ---- Permissions ----

  editPermissions(folder: Folder): void {
    const modal = this.modalService.open(PermissionsDialogComponent, {
      backdrop: 'static',
    })
    const dialog = modal.componentInstance as PermissionsDialogComponent
    dialog.object = folder
    modal.componentInstance.confirmClicked.subscribe(
      ({ permissions, merge }) => {
        modal.componentInstance.buttonsEnabled = false
        const updatedFolder = { ...folder }
        updatedFolder.owner = permissions['owner']
        updatedFolder['set_permissions'] = permissions['set_permissions']
        this.folderService.patch(updatedFolder).subscribe({
          next: () => {
            this.toastService.showInfo($localize`Folder permissions updated`)
            modal.close()
            this.loadFolders()
          },
          error: (e) => {
            this.toastService.showError(
              $localize`Error updating folder permissions`,
              e
            )
          },
        })
      }
    )
  }
}
