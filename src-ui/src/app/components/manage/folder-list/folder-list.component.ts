import { Component, QueryList, Renderer2, ViewChildren } from '@angular/core'
import { NgbModal, NgbPopover } from '@ng-bootstrap/ng-bootstrap'
import { FolderService } from 'src/app/services/rest/folder.service'
import { ToastService } from 'src/app/services/toast.service'
import { FolderEditDialogComponent } from '../../common/edit-dialog/folder-edit-dialog/folder-edit-dialog.component'
import { Folder } from 'src/app/data/folder'
import { ActivatedRoute, Router } from '@angular/router'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_HAS_FOLDER_ANY } from 'src/app/data/filter-rule-type'
import { PermissionsService, PermissionType } from 'src/app/services/permissions.service'

import { DocumentService } from '../../../services/rest/document.service'
import { Document } from '../../../data/document'
import { ManagementListComponent } from '../management-list/management-list.component'
import { takeUntil } from 'rxjs/operators'
import { BulkEditObjectOperation } from '../../../services/rest/abstract-name-filter-service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { SharedService } from '../../../shared.service'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'


@Component({
  selector: 'pngx-folders',
  templateUrl: './folder-list.component.html',
  styleUrls: ['./folder-list.component.scss'],
})
export class FoldersComponent extends ManagementListComponent<Folder> {
  public selectedObjects: Set<number> = new Set()
  public id: number
  displayMode = 'details'

  constructor(
    private sharedService: SharedService,
    private route: ActivatedRoute,
    private router: Router,
    public folderService: FolderService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService,
    private renderer: Renderer2,
    public documentService: DocumentService,
    private customDatePipe: CustomDatePipe,
  ) {
    function formatBytes(bytes, decimals = 2) {
      if (!+bytes) return '0 Bytes'

      const k = 1024
      const dm = decimals < 0 ? 0 : decimals
      const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']

      const i = Math.floor(Math.log(bytes) / Math.log(k))

      return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
    }

    super(
      folderService,
      modalService,
      FolderEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_FOLDER_ANY,
      $localize`file`,
      $localize`files`,
      PermissionType.Folder,
      [{
        key: 'filesize',
        name: $localize`Size`,
        valueFn: (item) => (item.type == 'file') ? formatBytes(item.filesize) : '',
        rendersHtml: true,
      },
        {
          key: 'modified',
          name: $localize`modified`,
          valueFn: (item) => this.customDatePipe.transform(item.modified),
          rendersHtml: true,
        }],
    )
  }

  @ViewChildren('popover') popovers: QueryList<NgbPopover>
  popover: NgbPopover
  mouseOnPreview = false
  popoverHidden = true
  public folderPath: Folder[] = []
  public folderCut: number[] = []
  public isFolderCutClicked = false
  public preFolder: number = null

  ngOnInit(): void {
    if (localStorage.getItem('folder-list:displayMode') != null) {
      this.displayMode = localStorage.getItem('folder-list:displayMode')
    }
    // this.reloadData()
    super.ngOnInit()

    this.route.paramMap.subscribe(() => {
      this.reloadData() // Gọi hàm để tải lại dữ liệu
    })
    this.sharedService.reloadData$.subscribe(() => {
      this.reloadData() // Gọi hàm để tải lại dữ liệu
    })


  }

  isSelected(object) {
    return this.selectedObjects.has(object.id)
  }

  saveDisplayMode() {
    localStorage.setItem('folder-list:displayMode', this.displayMode)
  }

  selectAll() {

    this.selectedObjects = new Set(this.data.map((o) => o.id))
  }


  extractDocuments(): void {
    this.documents = this.data
      .filter(item => item.document)  // Lọc các phần tử có `document`
      .map(item => item.document)    // Chỉ lấy phần `document` của các phần tử
  }

  reloadData() {
    this.reloadDataOveride()
  }

  async reloadDataOveride() {
    await this.route.paramMap.subscribe(params => {
      this.id = params.get('id') !== 'root' ? Number(params.get('id')) : null
    })
    // this.id = this.route.snapshot.params['id'] !== 'root' ? this.route.snapshot.params['id'] :  null;

    if (this.id != this.preFolder)
      this.page = 1
    this.selectedObjects.clear()
    let listFolderPath
    if (this.id) {
      this.folderService.getFolderPath(this.id).subscribe(
        (folder) => {
          listFolderPath = folder
          // console.log(listFolderPath)
          this.folderPath = listFolderPath.results
        })
    }
    // console.log(this.folderPath)
    this.isLoading = true
    let params = {}
    if (typeof this.id === 'number') {
      params['parent_folder__id'] = this.id
    } else {
      params['parent_folder__isnull'] = true
    }
    if (this.nameFilter) {
      params['name__icontains'] = this.nameFilter
    }
    // if (fullPerms) {
    //   params['full_perms'] = true
    // }
    // params['type__iexact'] = 'folder'
    // this.isLoading = true
    this.getService()
      .listFilteredCustom(
        this.page,
        null,
        this.sortField,
        params,
        this.sortReverse,
        this.nameFilter,
        true,
      )
      .pipe(takeUntil(this.getUnsubscribeNotifier()))
      .subscribe((c) => {
        this.data = c.results
        this.extractDocuments()
        this.collectionSize = c.count
        this.isLoading = false
      })

    this.preFolder = this.id
  }


  getPreviewUrl(document: Document): string {
    return this.documentService.getPreviewUrl(document.id)
  }

  mouseEnterPreviewButton(doc: Document) {
    const newPopover = this.popovers.get(this.documents.indexOf(doc))
    if (this.popover !== newPopover && this.popover?.isOpen())
      this.popover.close()
    this.popover = newPopover
    this.mouseOnPreview = true
    if (!this.popover.isOpen()) {

      this.popoverHidden = true
      setTimeout(() => {
        if (this.mouseOnPreview) {
          // show popover
          this.popover.open()
          this.popoverHidden = false
        } else {
          this.popover.close()
        }
      }, 600)
    }
  }

  mouseLeavePreviewButton() {
    this.mouseOnPreview = false
    this.maybeClosePopover()
  }

  maybeClosePopover() {
    setTimeout(() => {
      if (!this.mouseOnPreview) this.popover?.close()
    }, 600)
  }

  mouseLeavePreview() {
    this.mouseOnPreview = false
    this.maybeClosePopover()
  }

  mouseEnterPreview() {
    this.mouseOnPreview = true
  }

  getFolderSelect() {
    let folderIds = this.route.snapshot.queryParams['folderIds'] || []
    return Array.from(folderIds).join('').length
  }

  goToFolder(object: Folder) {
    let folderId = this.route.snapshot.queryParams['folderIds']
    let getQueryParams: { folderIds?: string }

    if (this.isFolderCutClicked) {
      getQueryParams = {
        folderIds: Array.from(this.folderCut).join(','),
      }
    } else if (folderId) {
      getQueryParams = {
        folderIds: Array.from(folderId).join(''),
      }
    } else {
      getQueryParams = {}
    }

    this.id = object?.id

    this.router.navigate(['/folders/', object.id],
      {
        queryParams: getQueryParams,
      },
    )
    this.reloadData()

  }

  cutFolder() {
    this.folderCut = Array.from(this.selectedObjects)
    this.isFolderCutClicked = true
    return this.folderCut
  }

  goToFolderRoot() {
    let folderId = this.route.snapshot.queryParams['folderIds']
    let getQueryParams: { folderIds?: string }

    if (this.isFolderCutClicked) {
      getQueryParams = {
        folderIds: Array.from(this.folderCut).join(','),
      }
    } else if (folderId) {
      getQueryParams = {
        folderIds: Array.from(folderId).join(''),
      }
    } else {
      getQueryParams = {}
    }
    this.id = null
    this.folderPath = []
    this.page = 1
    this.router.navigate(['/folders/root'], {
      queryParams: getQueryParams,
    })

    this.reloadData()

  }

  getCutFolder() {
    let folderIds
    this.route.queryParams.subscribe(params => {
      folderIds = params['folderIds']
    })
    const parts = folderIds.split(',')
    this.folderCut = parts.map(part => parseInt(part, 10))
    return this.folderCut
  }

  isSidebarVisible: boolean = false // Biến để theo dõi trạng thái của sidebar
  buttonLabel = $localize`Show Tree`

  toggleSidebar(event) {
    const btnElement = event.target as HTMLElement
    const svgElement = btnElement?.querySelector('svg')
    // const spanElement = btnElement?.querySelector('span')
    // console.log(btnElement)
    if (svgElement.style.transform != '') {
      this.renderer.removeStyle(svgElement, 'transform')
      // this.renderer.setValue(btnElement,'Show tree')

    } else {
      this.renderer.setStyle(svgElement, 'transform', 'rotate(180deg)')
      // this.renderer.setValue(btnElement,'Hidden tree')
      this.renderer.setStyle(svgElement, 'transition', 'transform 0.3s ease')
    }
    // // this.renderer.setStyle(svgElement, 'transition', 'transform 0.3s ease')
    this.buttonLabel = !this.isSidebarVisible ? $localize`Hide Tree` : $localize`Show Tree`
    this.isSidebarVisible = !this.isSidebarVisible // Đảo ngược trạng thái khi nhấn nút
  }

  cancelFolder() {
    this.reloadData()
    this.folderCut = []
    this.isFolderCutClicked = false
    if (this.router.url.includes('/folders/')) {
      this.id = this.route.snapshot.params['id']

      this.router.navigate(['/folders/', this.id], {
        queryParams: {},
      })
    }
  }

  update() {
    this.id = this.route.snapshot.params['id']
    let modal = this.getModalService().open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm update`
    modal.componentInstance.messageBold = $localize`This operation will permanently update all objects.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    this.folderCut = []
    this.isFolderCutClicked = false
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.getService()
        .bulk_edit_folders(
          Array.from(this.getCutFolder()),
          Number(this.id),
          BulkEditObjectOperation.Update,
        )
        .subscribe({
          next: () => {
            modal.close()
            this.getToastService().showInfo($localize`Objects update successfully`)

            if (this.router.url.includes('/folders/')) {
              this.router.navigate(['/folders/', this.id], {
                queryParams: {},
              })
              this.reloadData()
            } else {
              this.router.navigate(['/folders/root'], {
                queryParams: {},
              })
            }

          },
          error: (error) => {
            modal.componentInstance.buttonsEnabled = true
            this.getToastService().showError(
              $localize`Error updating objects`,
              error,
            )
          },
        })
    })
  }

  openCreateDialog() {
    var activeModal = this.getModalService().open(this.getEditDialogComponent(), {
      backdrop: 'static',
    })
    activeModal.componentInstance.object = { parent_folder: this.id }
    activeModal.componentInstance.dialogMode = EditDialogMode.CREATE
    activeModal.componentInstance.succeeded.subscribe(() => {
      this.reloadData()
      this.getToastService().showInfo(
        $localize`Successfully created ${this.typeName}.`,
      )
    })
    activeModal.componentInstance.failed.subscribe((e) => {
      this.getToastService().showError(
        $localize`Error occurred while creating ${this.typeName}.`,
        e,
      )
    })
  }

  getDeleteMessage(object: Folder) {
    if (object.type == 'folder')
      return $localize`Do you really want to delete the folder "${object.name}"?`
    return $localize`Do you really want to delete the file "${object.name}"?`

  }

  getDeleteMassageContent() {
    return $localize`Associated documents will be move to trash.`
  }
}
