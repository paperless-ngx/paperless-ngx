import { MatchingModel } from './matching-model';
import { ObjectWithId } from './object-with-id';


export const TAG_COLOURS = [
    { id: "", name: "Auto", textColor: "#000000" },
    { id: "#a6cee3", name: $localize`Light blue`, textColor: "#000000" },
    { id: "#1f78b4", name: $localize`Blue`, textColor: "#ffffff" },
    { id: "#b2df8a", name: $localize`Light green`, textColor: "#000000" },
    { id: "#33a02c", name: $localize`Green`, textColor: "#ffffff" },
    { id: "#fb9a99", name: $localize`Light red`, textColor: "#000000" },
    { id: "#e31a1c", name: $localize`Red `, textColor: "#ffffff" },
    { id: "#fdbf6f", name: $localize`Light orange`, textColor: "#000000" },
    { id: "#ff7f00", name: $localize`Orange`, textColor: "#000000" },
    { id: "#cab2d6", name: $localize`Light violet`, textColor: "#000000" },
    { id: "#6a3d9a", name: $localize`Violet`, textColor: "#ffffff" },
    { id: "#b15928", name: $localize`Brown`, textColor: "#ffffff" },
    { id: "#000000", name: $localize`Black`, textColor: "#ffffff" },
    { id: "#cccccc", name: $localize`Light grey`, textColor: "#000000" }
]

export interface PaperlessTag extends MatchingModel {

    colour?: string

    is_inbox_tag?: boolean

}
