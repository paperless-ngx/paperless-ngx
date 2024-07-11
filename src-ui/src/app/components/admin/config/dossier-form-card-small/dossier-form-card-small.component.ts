import {
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
} from '@angular/core'
import { map } from 'rxjs/operators'
import { Subject, takeUntil } from 'rxjs'
import { Document } from 'src/app/data/document'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { ToastService } from 'src/app/services/toast.service'
import { DocumentApproval } from 'src/app/data/document-approval'
import { Dossier } from 'src/app/data/dossier'
import { PermissionType } from 'src/app/services/permissions.service'
import { ColorTheme } from 'ngx-bootstrap-icons'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'

@Component({
  selector: 'pngx-dossier-form-card-small',
  templateUrl: './dossier-form-card-small.component.html',
  styleUrls: ['./dossier-form-card-small.component.scss'],
})
export class DossierFormCardSmallComponent extends ComponentWithPermissions {
  constructor(
    private documentService: DocumentService,
    // public settingsService: SettingsService,
    private modalService: NgbModal,
    private toastService: ToastService,
    // public permissionType: PermissionType,
  ) {
    super()
  }


  @Input()
  selected = false
  @Input()
  typeName: String
  @Input()
  selectedObjects: Set<number>

  @Output()
  toggleSelected = new EventEmitter()
  @Output() 
  filterDocuments = new EventEmitter<any>();
  @Output() 
  goToDossier = new EventEmitter<any>();
  @Output() 
  openEditDialog = new EventEmitter<any>();
  @Output() 
  openDeleteDialog = new EventEmitter<any>();
  @Output() 
  userCanEdit=new EventEmitter<any>();
  @Output() 
  userCanDelete=new EventEmitter<any>();
  // @Input() permissionType: PermissionType;
  @Input()
  dossier: Dossier

  @Output()
  dblClickDocument = new EventEmitter()

  @Output()
  clickTag = new EventEmitter<number>()
  ColorTheme = ColorTheme;

  moreTags: number = null

  


  mouseOnPreview = false
  popoverHidden = true
  
  // getIsThumbInverted() {
  //   return this.settingsService.get(SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED)
  // }

  

  get privateName() {
    return $localize`Private`
  }

  getThumbUrl(object: Dossier) {
    return this.documentService.getThumbUrl(1)
  }
  // get notesEnabled(): boolean {
  //   return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  // }

  editField() {
    // this.documentApproval = {
    //   id: undefined,
    //   access_type: null,
    //   status: undefined,
    //   submitted_by: null,
    //   object_pk: this.document.id.toString(),
    //   created: undefined,
    //   modified: undefined,
    //   expiration: null,
    //   ctype: 14,
    //   submitted_by_group: [],
    //   name: undefined,
    // }

    // const modal = this.modalService.open(ApprovalEditDialogComponent)
    // modal.componentInstance.dialogMode = EditDialogMode.CREATE
    // modal.componentInstance.object = this.documentApproval
    // modal.componentInstance.succeeded
    //   .pipe(takeUntil(this.unsubscribeNotifier))
    //   .subscribe((newField) => {
    //     this.toastService.showInfo($localize`Successfully sent mining request to "${newField.name}".`)
    //     // this.documentService.clearCache()
    //     // this.reload()
    //   })
    // modal.componentInstance.failed
    //   .pipe(takeUntil(this.unsubscribeNotifier))
    //   .subscribe((e) => {
    //     this.toastService.showError($localize`Error saving fieldSubmitted mining request failed.`, e)
    //   })
  }
}
