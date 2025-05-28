import { Injectable } from '@angular/core'
import { TreeNode } from 'primeng/api'

@Injectable()
export class NodeService {
    getTreeNodesData() {
        return [
            {
                key: '0',
                label: 'Documents',
                data: 'Documents Folder',
                icon: 'pi pi-fw pi-inbox',
                children: [
                    {
                        key: '0-0',
                        label: 'Work',
                        data: 'Work Folder',
                        icon: 'pi pi-fw pi-cog',
                        children: [
                            {
                                key: '0-0-0',
                                label: 'Expenses.doc',
                                icon: 'pi pi-fw pi-file',
                                data: 'Expenses Document',
                            },
                            { key: '0-0-1', label: 'Resume.doc', icon: 'pi pi-fw pi-file', data: 'Resume Document' },
                        ],
                    },
                    {
                        key: '0-1',
                        label: 'Home',
                        data: 'Home Folder',
                        icon: 'pi pi-fw pi-home',
                        children: [{
                            key: '0-1-0',
                            label: 'Invoices.txt',
                            icon: 'pi pi-fw pi-file',
                            data: 'Invoices for this month',
                        }],
                    },
                ],
            },
            {
                key: '1',
                label: 'Events',
                data: 'Events Folder',
                icon: 'pi pi-fw pi-calendar',
                children: [
                    { key: '1-0', label: 'Meeting', icon: 'pi pi-fw pi-calendar-plus', data: 'Meeting' },
                    { key: '1-1', label: 'Product Launch', icon: 'pi pi-fw pi-calendar-plus', data: 'Product Launch' },
                    { key: '1-2', label: 'Report Review', icon: 'pi pi-fw pi-calendar-plus', data: 'Report Review' },
                ],
            },
            {
                key: '2',
                label: 'Movies',
                data: 'Movies Folder',
                icon: 'pi pi-fw pi-star-fill',
                children: [
                    {
                        key: '2-0',
                        icon: 'pi pi-fw pi-star-fill',
                        label: 'Al Pacino',
                        data: 'Pacino Movies',
                        children: [
                            { key: '2-0-0', label: 'Scarface', icon: 'pi pi-fw pi-video', data: 'Scarface Movie' },
                            { key: '2-0-1', label: 'Serpico', icon: 'pi pi-fw pi-video', data: 'Serpico Movie' },
                        ],
                    },
                    {
                        key: '2-1',
                        label: 'Robert De Niro',
                        icon: 'pi pi-fw pi-star-fill',
                        data: 'De Niro Movies',
                        children: [
                            { key: '2-1-0', label: 'Goodfellas', icon: 'pi pi-fw pi-video', data: 'Goodfellas Movie' },
                            {
                                key: '2-1-1',
                                label: 'Untouchables',
                                icon: 'pi pi-fw pi-video',
                                data: 'Untouchables Movie',
                            },
                        ],
                    },
                ],
            },
        ]
    }

    getTreeTableNodesData() {
        return [
            {
                key: '0',
                data: {
                    name: 'Applications',
                    size: '100kb',
                    type: 'Folder',
                },
                children: [
                    {
                        key: '0-0',
                        data: {
                            name: 'Angular',
                            size: '25kb',
                            type: 'Folder',
                        },
                        children: [
                            {
                                key: '0-0-0',
                                data: {
                                    name: 'angular.app',
                                    size: '10kb',
                                    type: 'Application',
                                },
                            },
                            {
                                key: '0-0-1',
                                data: {
                                    name: 'native.app',
                                    size: '10kb',
                                    type: 'Application',
                                },
                            },
                            {
                                key: '0-0-2',
                                data: {
                                    name: 'mobile.app',
                                    size: '5kb',
                                    type: 'Application',
                                },
                            },
                        ],
                    },
                    {
                        key: '0-1',
                        data: {
                            name: 'editor.app',
                            size: '25kb',
                            type: 'Application',
                        },
                    },
                    {
                        key: '0-2',
                        data: {
                            name: 'settings.app',
                            size: '50kb',
                            type: 'Application',
                        },
                    },
                ],
            },
            {
                key: '1',
                data: {
                    name: 'Cloud',
                    size: '20kb',
                    type: 'Folder',
                },
                children: [
                    {
                        key: '1-0',
                        data: {
                            name: 'backup-1.zip',
                            size: '10kb',
                            type: 'Zip',
                        },
                    },
                    {
                        key: '1-1',
                        data: {
                            name: 'backup-2.zip',
                            size: '10kb',
                            type: 'Zip',
                        },
                    },
                ],
            },
            {
                key: '2',
                data: {
                    name: 'Desktop',
                    size: '150kb',
                    type: 'Folder',
                },
                children: [
                    {
                        key: '2-0',
                        data: {
                            name: 'note-meeting.txt',
                            size: '50kb',
                            type: 'Text',
                        },
                    },
                    {
                        key: '2-1',
                        data: {
                            name: 'note-todo.txt',
                            size: '100kb',
                            type: 'Text',
                        },
                    },
                ],
            },
            {
                key: '3',
                data: {
                    name: 'Documents',
                    size: '75kb',
                    type: 'Folder',
                },
                children: [
                    {
                        key: '3-0',
                        data: {
                            name: 'Work',
                            size: '55kb',
                            type: 'Folder',
                        },
                        children: [
                            {
                                key: '3-0-0',
                                data: {
                                    name: 'Expenses.doc',
                                    size: '30kb',
                                    type: 'Document',
                                },
                            },
                            {
                                key: '3-0-1',
                                data: {
                                    name: 'Resume.doc',
                                    size: '25kb',
                                    type: 'Resume',
                                },
                            },
                        ],
                    },
                    {
                        key: '3-1',
                        data: {
                            name: 'Home',
                            size: '20kb',
                            type: 'Folder',
                        },
                        children: [
                            {
                                key: '3-1-0',
                                data: {
                                    name: 'Invoices',
                                    size: '20kb',
                                    type: 'Text',
                                },
                            },
                        ],
                    },
                ],
            },
            {
                key: '4',
                data: {
                    name: 'Downloads',
                    size: '25kb',
                    type: 'Folder',
                },
                children: [
                    {
                        key: '4-0',
                        data: {
                            name: 'Spanish',
                            size: '10kb',
                            type: 'Folder',
                        },
                        children: [
                            {
                                key: '4-0-0',
                                data: {
                                    name: 'tutorial-a1.txt',
                                    size: '5kb',
                                    type: 'Text',
                                },
                            },
                            {
                                key: '4-0-1',
                                data: {
                                    name: 'tutorial-a2.txt',
                                    size: '5kb',
                                    type: 'Text',
                                },
                            },
                        ],
                    },
                    {
                        key: '4-1',
                        data: {
                            name: 'Travel',
                            size: '15kb',
                            type: 'Text',
                        },
                        children: [
                            {
                                key: '4-1-0',
                                data: {
                                    name: 'Hotel.pdf',
                                    size: '10kb',
                                    type: 'PDF',
                                },
                            },
                            {
                                key: '4-1-1',
                                data: {
                                    name: 'Flight.pdf',
                                    size: '5kb',
                                    type: 'PDF',
                                },
                            },
                        ],
                    },
                ],
            },
            {
                key: '5',
                data: {
                    name: 'Main',
                    size: '50kb',
                    type: 'Folder',
                },
                children: [
                    {
                        key: '5-0',
                        data: {
                            name: 'bin',
                            size: '50kb',
                            type: 'Link',
                        },
                    },
                    {
                        key: '5-1',
                        data: {
                            name: 'etc',
                            size: '100kb',
                            type: 'Link',
                        },
                    },
                    {
                        key: '5-2',
                        data: {
                            name: 'var',
                            size: '100kb',
                            type: 'Link',
                        },
                    },
                ],
            },
            {
                key: '6',
                data: {
                    name: 'Other',
                    size: '5kb',
                    type: 'Folder',
                },
                children: [
                    {
                        key: '6-0',
                        data: {
                            name: 'todo.txt',
                            size: '3kb',
                            type: 'Text',
                        },
                    },
                    {
                        key: '6-1',
                        data: {
                            name: 'logo.png',
                            size: '2kb',
                            type: 'Picture',
                        },
                    },
                ],
            },
            {
                key: '7',
                data: {
                    name: 'Pictures',
                    size: '150kb',
                    type: 'Folder',
                },
                children: [
                    {
                        key: '7-0',
                        data: {
                            name: 'barcelona.jpg',
                            size: '90kb',
                            type: 'Picture',
                        },
                    },
                    {
                        key: '7-1',
                        data: {
                            name: 'primeng.png',
                            size: '30kb',
                            type: 'Picture',
                        },
                    },
                    {
                        key: '7-2',
                        data: {
                            name: 'prime.jpg',
                            size: '30kb',
                            type: 'Picture',
                        },
                    },
                ],
            },
            {
                key: '8',
                data: {
                    name: 'Videos',
                    size: '1500kb',
                    type: 'Folder',
                },
                children: [
                    {
                        key: '8-0',
                        data: {
                            name: 'primefaces.mkv',
                            size: '1000kb',
                            type: 'Video',
                        },
                    },
                    {
                        key: '8-1',
                        data: {
                            name: 'intro.avi',
                            size: '500kb',
                            type: 'Video',
                        },
                    },
                ],
            },
        ]
    }

    getLazyNodesData() {
        return [
            {
                label: 'Lazy Node 0',
                data: 'Node 0',
                expandedIcon: 'pi pi-folder-open',
                collapsedIcon: 'pi pi-folder',
                leaf: false,
            },
            {
                label: 'Lazy Node 1',
                data: 'Node 1',
                expandedIcon: 'pi pi-folder-open',
                collapsedIcon: 'pi pi-folder',
                leaf: false,
            },
            {
                label: 'Lazy Node 1',
                data: 'Node 2',
                expandedIcon: 'pi pi-folder-open',
                collapsedIcon: 'pi pi-folder',
                leaf: false,
            },
        ]
    }

    getFileSystemNodesData() {
        return [
            {
                data: {
                    name: 'Applications',
                    size: '200mb',
                    type: 'Folder',
                },
                children: [
                    {
                        data: {
                            name: 'Angular',
                            size: '25mb',
                            type: 'Folder',
                        },
                        children: [
                            {
                                data: {
                                    name: 'angular.app',
                                    size: '10mb',
                                    type: 'Application',
                                },
                            },
                            {
                                data: {
                                    name: 'cli.app',
                                    size: '10mb',
                                    type: 'Application',
                                },
                            },
                            {
                                data: {
                                    name: 'mobile.app',
                                    size: '5mb',
                                    type: 'Application',
                                },
                            },
                        ],
                    },
                    {
                        data: {
                            name: 'editor.app',
                            size: '25mb',
                            type: 'Application',
                        },
                    },
                    {
                        data: {
                            name: 'settings.app',
                            size: '50mb',
                            type: 'Application',
                        },
                    },
                ],
            },
            {
                data: {
                    name: 'Cloud',
                    size: '20mb',
                    type: 'Folder',
                },
                children: [
                    {
                        data: {
                            name: 'backup-1.zip',
                            size: '10mb',
                            type: 'Zip',
                        },
                    },
                    {
                        data: {
                            name: 'backup-2.zip',
                            size: '10mb',
                            type: 'Zip',
                        },
                    },
                ],
            },
            {
                data: {
                    name: 'Desktop',
                    size: '150kb',
                    type: 'Folder',
                },
                children: [
                    {
                        data: {
                            name: 'note-meeting.txt',
                            size: '50kb',
                            type: 'Text',
                        },
                    },
                    {
                        data: {
                            name: 'note-todo.txt',
                            size: '100kb',
                            type: 'Text',
                        },
                    },
                ],
            },
            {
                data: {
                    name: 'Documents',
                    size: '75kb',
                    type: 'Folder',
                },
                children: [
                    {
                        data: {
                            name: 'Work',
                            size: '55kb',
                            type: 'Folder',
                        },
                        children: [
                            {
                                data: {
                                    name: 'Expenses.doc',
                                    size: '30kb',
                                    type: 'Document',
                                },
                            },
                            {
                                data: {
                                    name: 'Resume.doc',
                                    size: '25kb',
                                    type: 'Resume',
                                },
                            },
                        ],
                    },
                    {
                        data: {
                            name: 'Home',
                            size: '20kb',
                            type: 'Folder',
                        },
                        children: [
                            {
                                data: {
                                    name: 'Invoices',
                                    size: '20kb',
                                    type: 'Text',
                                },
                            },
                        ],
                    },
                ],
            },
            {
                data: {
                    name: 'Downloads',
                    size: '25mb',
                    type: 'Folder',
                },
                children: [
                    {
                        data: {
                            name: 'Spanish',
                            size: '10mb',
                            type: 'Folder',
                        },
                        children: [
                            {
                                data: {
                                    name: 'tutorial-a1.txt',
                                    size: '5mb',
                                    type: 'Text',
                                },
                            },
                            {
                                data: {
                                    name: 'tutorial-a2.txt',
                                    size: '5mb',
                                    type: 'Text',
                                },
                            },
                        ],
                    },
                    {
                        data: {
                            name: 'Travel',
                            size: '15mb',
                            type: 'Text',
                        },
                        children: [
                            {
                                data: {
                                    name: 'Hotel.pdf',
                                    size: '10mb',
                                    type: 'PDF',
                                },
                            },
                            {
                                data: {
                                    name: 'Flight.pdf',
                                    size: '5mb',
                                    type: 'PDF',
                                },
                            },
                        ],
                    },
                ],
            },
            {
                data: {
                    name: 'Main',
                    size: '50mb',
                    type: 'Folder',
                },
                children: [
                    {
                        data: {
                            name: 'bin',
                            size: '50kb',
                            type: 'Link',
                        },
                    },
                    {
                        data: {
                            name: 'etc',
                            size: '100kb',
                            type: 'Link',
                        },
                    },
                    {
                        data: {
                            name: 'var',
                            size: '100kb',
                            type: 'Link',
                        },
                    },
                ],
            },
            {
                data: {
                    name: 'Other',
                    size: '5mb',
                    type: 'Folder',
                },
                children: [
                    {
                        data: {
                            name: 'todo.txt',
                            size: '3mb',
                            type: 'Text',
                        },
                    },
                    {
                        data: {
                            name: 'logo.png',
                            size: '2mb',
                            type: 'Picture',
                        },
                    },
                ],
            },
            {
                data: {
                    name: 'Pictures',
                    size: '150kb',
                    type: 'Folder',
                },
                children: [
                    {
                        data: {
                            name: 'barcelona.jpg',
                            size: '90kb',
                            type: 'Picture',
                        },
                    },
                    {
                        data: {
                            name: 'primeng.png',
                            size: '30kb',
                            type: 'Picture',
                        },
                    },
                    {
                        data: {
                            name: 'prime.jpg',
                            size: '30kb',
                            type: 'Picture',
                        },
                    },
                ],
            },
            {
                data: {
                    name: 'Videos',
                    size: '1500mb',
                    type: 'Folder',
                },
                children: [
                    {
                        data: {
                            name: 'primefaces.mkv',
                            size: '1000mb',
                            type: 'Video',
                        },
                    },
                    {
                        data: {
                            name: 'intro.avi',
                            size: '500mb',
                            type: 'Video',
                        },
                    },
                ],
            },
        ]
    }

    getDynamicTreeNodes(parentCount: number, childrenCount: number): TreeNode[] {
        const nodes: TreeNode[] = []

        for (let parentIndex = 0; parentIndex < parentCount; parentIndex++) {
            const children: TreeNode[] = []

            for (let childIndex = 0; childIndex < childrenCount; childIndex++) {
                children.push({
                    key: `${parentIndex}-${childIndex}`,
                    label: `Child ${parentIndex}-${childIndex}`,
                    selectable: true,
                })
            }

            nodes.push({
                key: parentIndex.toString(),
                label: `Parent ${parentIndex}`,
                selectable: true,
                children: children,
            })
        }

        return nodes
    }

    getLargeTreeNodes() {
        return Promise.resolve(this.getDynamicTreeNodes(10, 100))
    }

    getTreeTableNodes() {
        return Promise.resolve(this.getTreeTableNodesData())
    }

    getTreeNodes() {
        return Promise.resolve(this.getTreeNodesData())
    }

    getFiles() {
        return Promise.resolve(this.getTreeNodesData())
    }

    getLazyFiles() {
        return Promise.resolve(this.getLazyNodesData())
    }

    getFilesystem() {
        return Promise.resolve(this.getFileSystemNodesData())
    }
}
