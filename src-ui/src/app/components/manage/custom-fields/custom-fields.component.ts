import { Component, OnInit } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject, takeUntil } from 'rxjs'
import { PermissionType, PermissionsService } from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { CustomFieldEditDialogComponent } from '../../common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { CustomField } from 'src/app/data/custom-field'
import { ManagementListComponent } from '../management-list/management-list.component'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_HAS_CUSTOM_FIELDS_ANY } from 'src/app/data/filter-rule-type'
import { CustomListComponent } from '../custom-list/custom-list.component'
import { CustomService } from 'src/app/services/common-service/service-custom'
import { ActivatedRoute } from '@angular/router'

@Component({
    selector: 'pngx-custom-fields',
    templateUrl: './../custom-list/custom-list.component.html',
    styleUrls: ['./../custom-list/custom-list.component.scss'],
})
export class CustomFieldsComponent extends CustomListComponent<CustomField> {
    constructor(
        customfieldsService: CustomFieldsService,
        modalService: NgbModal,
        toastService: ToastService,
        documentListViewService: DocumentListViewService,
        permissionsService: PermissionsService,
        customService: CustomService,
        route: ActivatedRoute
    ) {
        super(
            customfieldsService,
            modalService,
            CustomFieldEditDialogComponent,
            toastService,
            documentListViewService,
            permissionsService,
            FILTER_HAS_CUSTOM_FIELDS_ANY,
            $localize`customField`,
            $localize`customFields`,
            PermissionType.CustomField,
            [
                {
                    key: 'type',
                    name: $localize`Type`,
                    rendersHtml: true,
                    valueFn: (c: CustomField) => {
                        return c.type
                    },
                },
            ],
            customService,
            route
        )
    }

    getDeleteMessage(object: CustomField) {
        return $localize`Do you really want to delete the CustomField "${object.name}"?`
    }
}