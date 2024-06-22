import { Component, OnInit } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { Subject, takeUntil } from 'rxjs';
import { CustomField } from 'src/app/data/custom-field';
import { PermissionsService } from 'src/app/services/permissions.service';
import { ToastService } from 'src/app/services/toast.service';
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component';
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component';
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component';
import { KhoVatLyService } from 'src/app/services/rest/kho-vat-ly.service';
import { CustomFields, DATA_TYPE_LABELS } from 'src/app/data/customfields';
import { CustomShelfEditDialogComponent } from '../../common/custom-shelf-edit-dialog/custom-shelf-edit-dialog.component';


@Component({
    selector: 'pngx-kho-vat-ly',
    templateUrl: './kho-vat-ly.component.html',
    styleUrls: ['./kho-vat-ly.component.scss'],
})
export class KhoVatLyComponent
    extends ComponentWithPermissions
    implements OnInit {
    public fields: CustomField[] = [];

    private unsubscribeNotifier: Subject<any> = new Subject();
    constructor(
        private customFieldsService: KhoVatLyService,
        public permissionsService: PermissionsService,
        private modalService: NgbModal,
        private toastService: ToastService
    ) {
        super();
    }

    ngOnInit() {
        this.reload();
    }

    reload() {
        this.customFieldsService
            .listAll()
            .pipe(takeUntil(this.unsubscribeNotifier))
            .subscribe((r) => {
                this.fields = r.results;
            });
    }

    editField(field: CustomFields) {
        const modal = this.modalService.open(CustomShelfEditDialogComponent);
        modal.componentInstance.dialogMode = field
            ? EditDialogMode.EDIT
            : EditDialogMode.CREATE;
        modal.componentInstance.object = field;
        modal.componentInstance.succeeded
            .pipe(takeUntil(this.unsubscribeNotifier))
            .subscribe((newField) => {
                this.toastService.showInfo($localize`Saved field "${newField.name}".`);
                this.customFieldsService.clearCache();
                this.reload();
            });
        modal.componentInstance.failed
            .pipe(takeUntil(this.unsubscribeNotifier))
            .subscribe((e) => {
                this.toastService.showError($localize`Error saving field.`, e);
            });
    }

    deleteField(field: CustomFields) {
        const modal = this.modalService.open(ConfirmDialogComponent, {
            backdrop: 'static',
        });
        modal.componentInstance.title = $localize`Confirm delete field`;
        modal.componentInstance.messageBold = $localize`This operation will permanently delete this field.`;
        modal.componentInstance.message = $localize`This operation cannot be undone.`;
        modal.componentInstance.btnClass = 'btn-danger';
        modal.componentInstance.btnCaption = $localize`Proceed`;
        modal.componentInstance.confirmClicked.subscribe(() => {
            modal.componentInstance.buttonsEnabled = false;
            this.customFieldsService.delete(field).subscribe({
                next: () => {
                    modal.close();
                    this.toastService.showInfo($localize`Deleted field`);
                    this.customFieldsService.clearCache();
                    this.reload();
                },
                error: (e) => {
                    this.toastService.showError($localize`Error deleting field.`, e);
                },
            });
        });
    }

    getDataType(field: CustomFields): string {
        return DATA_TYPE_LABELS.find((l) => l.id === field.data_type).name;
    }
}
