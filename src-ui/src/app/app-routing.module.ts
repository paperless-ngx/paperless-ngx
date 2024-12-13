import { NgModule } from '@angular/core'
import { RouterModule, Routes } from '@angular/router'
import { ConfigComponent } from './components/admin/config/config.component'
import { LogsComponent } from './components/admin/logs/logs.component'
import { SettingsComponent } from './components/admin/settings/settings.component'
import { TasksComponent } from './components/admin/tasks/tasks.component'
import { TrashComponent } from './components/admin/trash/trash.component'
import { UsersAndGroupsComponent } from './components/admin/users-groups/users-groups.component'
import { AppFrameComponent } from './components/app-frame/app-frame.component'
import { DashboardComponent } from './components/dashboard/dashboard.component'
import { DocumentAsnComponent } from './components/document-asn/document-asn.component'
import { DocumentDetailComponent } from './components/document-detail/document-detail.component'
import { DocumentListComponent } from './components/document-list/document-list.component'
import { CorrespondentListComponent } from './components/manage/correspondent-list/correspondent-list.component'
import { CustomFieldsComponent } from './components/manage/custom-fields/custom-fields.component'
import { DocumentTypeListComponent } from './components/manage/document-type-list/document-type-list.component'
import { MailComponent } from './components/manage/mail/mail.component'
import { SavedViewsComponent } from './components/manage/saved-views/saved-views.component'
import { StoragePathListComponent } from './components/manage/storage-path-list/storage-path-list.component'
import { TagListComponent } from './components/manage/tag-list/tag-list.component'
import { WorkflowsComponent } from './components/manage/workflows/workflows.component'
import { NotFoundComponent } from './components/not-found/not-found.component'
import { DirtyDocGuard } from './guards/dirty-doc.guard'
import { DirtyFormGuard } from './guards/dirty-form.guard'
import { DirtySavedViewGuard } from './guards/dirty-saved-view.guard'
import { PermissionsGuard } from './guards/permissions.guard'
import {
  PermissionAction,
  PermissionType,
} from './services/permissions.service'

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  {
    path: '',
    component: AppFrameComponent,
    canDeactivate: [DirtyDocGuard],
    children: [
      { path: 'dashboard', component: DashboardComponent },
      {
        path: 'documents',
        component: DocumentListComponent,
        canDeactivate: [DirtySavedViewGuard],
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.Document,
          },
        },
      },
      {
        path: 'view/:id',
        component: DocumentListComponent,
        canDeactivate: [DirtySavedViewGuard],
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.SavedView,
          },
        },
      },
      {
        path: 'documents/:id',
        component: DocumentDetailComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.Document,
          },
        },
      },
      {
        path: 'documents/:id/:section',
        component: DocumentDetailComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.Document,
          },
        },
      },
      {
        path: 'asn/:id',
        component: DocumentAsnComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.Document,
          },
        },
      },
      {
        path: 'tags',
        component: TagListComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.Tag,
          },
        },
      },
      {
        path: 'documenttypes',
        component: DocumentTypeListComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.DocumentType,
          },
        },
      },
      {
        path: 'correspondents',
        component: CorrespondentListComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.Correspondent,
          },
        },
      },
      {
        path: 'storagepaths',
        component: StoragePathListComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.StoragePath,
          },
        },
      },
      {
        path: 'logs',
        component: LogsComponent,
        canActivate: [PermissionsGuard],
        data: {
          requireAdmin: true,
        },
      },
      {
        path: 'trash',
        component: TrashComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.Delete,
            type: PermissionType.Document,
          },
        },
      },
      // redirect old paths
      {
        path: 'settings/mail',
        redirectTo: '/mail',
      },
      {
        path: 'settings/usersgroups',
        redirectTo: '/usersgroups',
      },
      {
        path: 'settings/savedviews',
        redirectTo: '/savedviews',
      },
      {
        path: 'settings',
        component: SettingsComponent,
        canDeactivate: [DirtyFormGuard],
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.Change,
            type: PermissionType.UISettings,
          },
        },
      },
      {
        path: 'settings/:section',
        component: SettingsComponent,
        canDeactivate: [DirtyFormGuard],
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.UISettings,
          },
        },
      },
      {
        path: 'config',
        component: ConfigComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.Change,
            type: PermissionType.AppConfig,
          },
        },
      },
      {
        path: 'tasks',
        component: TasksComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.PaperlessTask,
          },
        },
      },
      {
        path: 'customfields',
        component: CustomFieldsComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.CustomField,
          },
        },
      },
      {
        path: 'workflows',
        component: WorkflowsComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.Workflow,
          },
        },
      },
      {
        path: 'mail',
        component: MailComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.MailAccount,
          },
        },
      },
      {
        path: 'usersgroups',
        component: UsersAndGroupsComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.User,
          },
        },
      },
      {
        path: 'savedviews',
        component: SavedViewsComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermission: {
            action: PermissionAction.View,
            type: PermissionType.SavedView,
          },
        },
      },
    ],
  },

  { path: '404', component: NotFoundComponent },
  { path: '**', redirectTo: '/404', pathMatch: 'full' },
]

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule],
})
export class AppRoutingModule {}
