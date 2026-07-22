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
import { DocumentAttributesComponent } from './components/manage/document-attributes/document-attributes.component'
import { MailComponent } from './components/manage/mail/mail.component'
import { SavedViewsComponent } from './components/manage/saved-views/saved-views.component'
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
      {
        path: 'dashboard',
        component: DashboardComponent,
        data: {
          componentName: 'AppFrameComponent',
        },
      },
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
          componentName: 'DocumentListComponent',
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
          componentName: 'DocumentListComponent',
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
          componentName: 'DocumentDetailComponent',
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
          componentName: 'DocumentDetailComponent',
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
          componentName: 'DocumentAsnComponent',
        },
      },
      {
        path: 'attributes',
        component: DocumentAttributesComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermissionAny: [
            { action: PermissionAction.View, type: PermissionType.Tag },
            {
              action: PermissionAction.View,
              type: PermissionType.Correspondent,
            },
            {
              action: PermissionAction.View,
              type: PermissionType.DocumentType,
            },
            { action: PermissionAction.View, type: PermissionType.StoragePath },
            { action: PermissionAction.View, type: PermissionType.CustomField },
          ],
          componentName: 'DocumentAttributesComponent',
        },
      },
      {
        path: 'attributes/:section',
        component: DocumentAttributesComponent,
        canActivate: [PermissionsGuard],
        data: {
          requiredPermissionAny: [
            { action: PermissionAction.View, type: PermissionType.Tag },
            {
              action: PermissionAction.View,
              type: PermissionType.Correspondent,
            },
            {
              action: PermissionAction.View,
              type: PermissionType.DocumentType,
            },
            { action: PermissionAction.View, type: PermissionType.StoragePath },
            { action: PermissionAction.View, type: PermissionType.CustomField },
          ],
          componentName: 'DocumentAttributesComponent',
        },
      },
      {
        path: 'documentproperties',
        redirectTo: '/attributes',
        pathMatch: 'full',
      },
      {
        path: 'documentproperties/:section',
        redirectTo: '/attributes/:section',
        pathMatch: 'full',
      },
      {
        path: 'tags',
        redirectTo: '/attributes/tags',
        pathMatch: 'full',
      },
      {
        path: 'correspondents',
        redirectTo: '/attributes/correspondents',
        pathMatch: 'full',
      },
      {
        path: 'documenttypes',
        redirectTo: '/attributes/documenttypes',
        pathMatch: 'full',
      },
      {
        path: 'storagepaths',
        redirectTo: '/attributes/storagepaths',
        pathMatch: 'full',
      },
      {
        path: 'logs',
        component: LogsComponent,
        canActivate: [PermissionsGuard],
        data: {
          requireAdmin: true,
          componentName: 'LogsComponent',
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
          componentName: 'TrashComponent',
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
          componentName: 'SettingsComponent',
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
          componentName: 'SettingsComponent',
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
          componentName: 'ConfigComponent',
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
          componentName: 'TasksComponent',
        },
      },
      {
        path: 'customfields',
        redirectTo: '/attributes/customfields',
        pathMatch: 'full',
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
          componentName: 'WorkflowsComponent',
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
          componentName: 'MailComponent',
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
          componentName: 'UsersAndGroupsComponent',
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
          componentName: 'SavedViewsComponent',
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
