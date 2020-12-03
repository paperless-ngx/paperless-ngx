import { MatchingModel } from './matching-model';
import { ObjectWithId } from './object-with-id';


export const TAG_COLOURS = [
    { id: "", name: "Auto", textColor: "#000000" },
    { id: "#a6cee3", name: "Light Blue", textColor: "#000000" },
    { id: "#1f78b4", name: "Blue", textColor: "#ffffff" },
    { id: "#b2df8a", name: "Light Green", textColor: "#000000" },
    { id: "#33a02c", name: "Green", textColor: "#000000" },
    { id: "#fb9a99", name: "Light Red", textColor: "#000000" },
    { id: "#e31a1c", name: "Red ", textColor: "#ffffff" },
    { id: "#fdbf6f", name: "Light Orange", textColor: "#000000" },
    { id: "#ff7f00", name: "Orange", textColor: "#000000" },
    { id: "#cab2d6", name: "Light Violet", textColor: "#000000" },
    { id: "#6a3d9a", name: "Violet", textColor: "#ffffff" },
    { id: "#b15928", name: "Brown", textColor: "#000000" },
    { id: "#000000", name: "Black", textColor: "#ffffff" },
    { id: "#cccccc", name: "Light Grey", textColor: "#000000" }
]

export interface PaperlessTag extends MatchingModel {

    colour?: string

    is_inbox_tag?: boolean

    document_count?: number
}
