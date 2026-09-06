import { Component, OnInit, inject, signal } from '@angular/core'
import { ActivatedRoute, Router, RouterModule } from '@angular/router'
import {
  NgbDropdownModule,
  NgbModal,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subscription, finalize, takeUntil } from 'rxjs'
import { EditDialogMode } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { FolderEditDialogComponent } from 'src/app/components/common/edit-dialog/folder-edit-dialog/folder-edit-dialog.component'
import { Document } from 'src/app/data/document'
import { Folder } from 'src/app/data/folder'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { FolderService } from 'src/app/services/rest/folder.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmButtonComponent } from '../common/confirm-button/confirm-button.component'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../loading-component/loading.component'

@Component({
  selector: 'pngx-folders',
  templateUrl: './folders.component.html',
  styleUrls: ['./folders.component.scss'],
  imports: [
    PageHeaderComponent,
    ConfirmButtonComponent,
    IfPermissionsDirective,
    CustomDatePipe,
    RouterModule,
    NgxBootstrapIconsModule,
    NgbDropdownModule,
    NgbPaginationModule,
  ],
})
export class FoldersComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  private folderService = inject(FolderService)
  private documentService = inject(DocumentService)
  private modalService = inject(NgbModal)
  private toastService = inject(ToastService)
  private route = inject(ActivatedRoute)
  private router = inject(Router)
  private permissionsService = inject(PermissionsService)

  public roots: Folder[] = []
  public foldersById: Map<number, Folder> = new Map()
  /** Flattened list (depth annotated) used by the sidebar tree and dropdowns */
  public flatFolders: Folder[] = []

  public currentFolder: Folder | null = null
  public subfolders: Folder[] = []

  public documents: Document[] = []
  public documentsCount: number = 0
  public page: number = 1
  public pageSize: number = 50
  public readonly documentsLoading = signal(false)

  public selected: Set<number> = new Set()
  public collapsedFolders: Set<number> = new Set()

  private draggedDocIds: number[] = []
  private documentsRequest?: Subscription
  public readonly moving = signal(false)
  public dropTarget: number | null = null
  public destinationSearch = ''

  get destinationFolders(): Folder[] {
    const search = this.destinationSearch.trim().toLocaleLowerCase()
    return this.flatFolders.filter((folder) =>
      (folder.full_path || folder.name || '')
        .toLocaleLowerCase()
        .includes(search)
    )
  }

  canMoveDocument(doc: Document): boolean {
    return (
      this.permissionsService.currentUserCan(
        this.PermissionAction.Change,
        this.PermissionType.Document
      ) &&
      this.permissionsService.currentUserHasObjectPermissions(
        this.PermissionAction.Change,
        doc
      )
    )
  }

  get visibleFlatFolders(): Folder[] {
    return this.flatFolders.filter(
      (folder) => !this.hasCollapsedAncestor(folder)
    )
  }

  ngOnInit(): void {
    this.reloadTree(() => {
      this.route.paramMap
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe((params) => {
          const id = params.get('id')
          if ((id ? +id : null) === (this.currentFolder?.id ?? null)) return
          if (id) {
            this.openFolder(this.foldersById.get(+id) ?? null, false)
          } else {
            this.openFolder(null, false)
          }
        })
    })
  }

  private flatten(folders: Folder[], depth: number): void {
    for (const folder of folders) {
      folder.depth = depth
      this.foldersById.set(folder.id, folder)
      this.flatFolders.push(folder)
      if (folder.children?.length) {
        this.flatten(folder.children, depth + 1)
      }
    }
  }

  private hasCollapsedAncestor(folder: Folder): boolean {
    let parentId = folder.parent
    const seen = new Set<number>()
    while (parentId && !seen.has(parentId)) {
      seen.add(parentId)
      if (this.collapsedFolders.has(parentId)) {
        return true
      }
      parentId = this.foldersById.get(parentId)?.parent
    }
    return false
  }

  reloadTree(callback?: () => void): void {
    this.loading.set(true)
    this.folderService.clearCache()
    this.folderService
      .getTree()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          this.roots = result.results
          this.foldersById = new Map()
          this.flatFolders = []
          this.flatten(this.roots, 0)
          this.collapsedFolders.forEach((folderId) => {
            if (!this.foldersById.has(folderId)) {
              this.collapsedFolders.delete(folderId)
            }
          })
          this.loading.set(false)
          this.show.set(true)
          // Refresh the current folder reference / contents
          if (this.currentFolder) {
            this.currentFolder =
              this.foldersById.get(this.currentFolder.id) ?? null
          }
          this.computeSubfolders()
          callback?.()
        },
        error: (e) => {
          this.loading.set(false)
          this.toastService.showError($localize`Error loading folders`, e)
        },
      })
  }

  private computeSubfolders(): void {
    this.subfolders = this.currentFolder
      ? (this.currentFolder.children ?? [])
      : this.roots
  }

  get breadcrumb(): Folder[] {
    if (!this.currentFolder) return []
    const crumbs: Folder[] = []
    let f: Folder | undefined = this.currentFolder
    const seen = new Set<number>()
    while (f && !seen.has(f.id)) {
      seen.add(f.id)
      crumbs.unshift(f)
      f = f.parent ? this.foldersById.get(f.parent) : undefined
    }
    return crumbs
  }

  openFolder(folder: Folder | null, updateUrl: boolean = true): void {
    this.documentsRequest?.unsubscribe()
    this.documentsLoading.set(false)
    this.documents = []
    this.documentsCount = 0
    this.currentFolder = folder
    this.selected.clear()
    this.page = 1
    this.destinationSearch = ''
    this.computeSubfolders()
    if (updateUrl) {
      this.router.navigate(folder ? ['/folders', folder.id] : ['/folders'])
    }
    if (folder) {
      this.loadDocuments()
    } else {
      this.documents = []
      this.documentsCount = 0
    }
  }

  loadDocuments(): void {
    this.documentsRequest?.unsubscribe()
    if (!this.currentFolder) return
    this.documentsLoading.set(true)
    this.documentsRequest = this.documentService
      .list(this.page, this.pageSize, 'created', true, {
        folder__id: this.currentFolder.id,
        truncate_content: true,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          this.documents = result.results
          this.documentsCount = result.count
          this.documentsLoading.set(false)
          if (!result.results.length && this.page > 1) {
            this.page = Math.max(1, Math.ceil(result.count / this.pageSize))
            this.loadDocuments()
          }
        },
        error: (e) => {
          this.documentsLoading.set(false)
          this.toastService.showError($localize`Error loading documents`, e)
        },
      })
  }

  onPageChange(page: number): void {
    this.selected.clear()
    this.page = page
    this.loadDocuments()
  }

  // --- Folder CRUD -----------------------------------------------------------

  createFolder(parent: Folder | null): void {
    const modal = this.modalService.open(FolderEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    modal.componentInstance.object = { parent: parent ? parent.id : null }
    modal.componentInstance.folders = this.roots
    modal.componentInstance.succeeded.subscribe(() => {
      this.toastService.showInfo($localize`Folder created.`)
      this.reloadTree()
    })
  }

  renameFolder(folder: Folder): void {
    const modal = this.modalService.open(FolderEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.EDIT
    modal.componentInstance.object = folder
    modal.componentInstance.folders = this.roots
    modal.componentInstance.succeeded.subscribe(() => {
      this.toastService.showInfo($localize`Folder updated.`)
      this.reloadTree()
    })
  }

  deleteFolder(folder: Folder): void {
    this.folderService.delete(folder).subscribe({
      next: () => {
        this.toastService.showInfo(
          $localize`Folder deleted. Its documents were moved to the parent folder.`
        )
        const parent = folder.parent
          ? this.foldersById.get(folder.parent)
          : null
        this.reloadTree(() => this.openFolder(parent ?? null))
      },
      error: (e) => {
        this.toastService.showError($localize`Error deleting folder`, e)
      },
    })
  }

  canDeleteFolder(folder: Folder): boolean {
    return (
      !folder.is_default &&
      this.permissionsService.currentUserCan(
        this.PermissionAction.Delete,
        this.PermissionType.Folder
      ) &&
      this.permissionsService.currentUserOwnsObject(folder)
    )
  }

  hasChildren(folder: Folder): boolean {
    return (folder.children?.length ?? 0) > 0
  }

  isCollapsed(folder: Folder): boolean {
    return this.collapsedFolders.has(folder.id)
  }

  toggleFolderCollapsed(folder: Folder): void {
    if (!this.hasChildren(folder)) return
    if (this.collapsedFolders.has(folder.id)) {
      this.collapsedFolders.delete(folder.id)
    } else {
      this.collapsedFolders.add(folder.id)
    }
  }

  getFolderHue(folder: Folder): number {
    return 205 + (((folder.depth ?? 0) * 33) % 115)
  }

  // --- Document selection ----------------------------------------------------

  isSelected(doc: Document): boolean {
    return this.selected.has(doc.id)
  }

  toggleSelected(doc: Document): void {
    if (this.moving() || !this.canMoveDocument(doc)) return
    if (this.selected.has(doc.id)) {
      this.selected.delete(doc.id)
    } else {
      this.selected.add(doc.id)
    }
  }

  get allSelected(): boolean {
    return (
      this.documents.some((doc) => this.canMoveDocument(doc)) &&
      this.documents
        .filter((doc) => this.canMoveDocument(doc))
        .every((doc) => this.selected.has(doc.id))
    )
  }

  toggleSelectAll(): void {
    if (this.moving()) return
    if (this.allSelected) {
      this.selected.clear()
    } else {
      this.documents
        .filter((doc) => this.canMoveDocument(doc))
        .forEach((d) => this.selected.add(d.id))
    }
  }

  // --- Move documents --------------------------------------------------------

  moveSelectedTo(folder: Folder): void {
    this.moveDocsTo(folder.id, Array.from(this.selected))
  }

  moveDocsTo(folderId: number, docIds: number[]): void {
    if (!docIds.length || this.moving() || folderId === this.currentFolder?.id)
      return
    this.moving.set(true)
    const destination = this.foldersById.get(folderId)?.name ?? String(folderId)
    this.documentService
      .bulkEdit({ documents: docIds }, 'set_folder', { folder: folderId })
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        finalize(() => {
          this.moving.set(false)
        })
      )
      .subscribe({
        next: () => {
          this.toastService.showInfo(
            $localize`Moved ${docIds.length} document(s) to ${destination}.`
          )
          this.selected.clear()
          this.documentService.clearCache()
          this.reloadTree()
          this.loadDocuments()
        },
        error: (e) => {
          this.toastService.showError($localize`Error moving documents`, e)
        },
      })
  }

  // --- Native drag & drop ----------------------------------------------------

  onDocDragStart(event: DragEvent, doc: Document): void {
    if (this.moving() || !this.canMoveDocument(doc)) {
      event.preventDefault()
      return
    }
    // If the dragged document is part of the current selection, move all
    // selected documents; otherwise move just this one.
    this.draggedDocIds =
      this.selected.size && this.selected.has(doc.id)
        ? Array.from(this.selected)
        : [doc.id]
    event.dataTransfer?.setData('text/plain', this.draggedDocIds.join(','))
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
  }

  onFolderDragOver(event: DragEvent, folder: Folder): void {
    if (
      this.draggedDocIds.length &&
      folder.id !== this.currentFolder?.id &&
      !this.moving()
    ) {
      event.preventDefault()
      this.dropTarget = folder.id
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
    }
  }

  onDragEnd(): void {
    this.draggedDocIds = []
    this.dropTarget = null
  }

  onFolderDrop(event: DragEvent, folder: Folder): void {
    event.preventDefault()
    event.stopPropagation()
    if (this.draggedDocIds.length) {
      this.moveDocsTo(folder.id, this.draggedDocIds)
      this.onDragEnd()
    }
  }

  trackByFolderId(index: number, folder: Folder): number {
    return folder.id
  }

  trackByDocId(index: number, doc: Document): number {
    return doc.id
  }
}
