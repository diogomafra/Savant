from typing import List, Tuple

from savant.deepstream.meta.frame import NvDsFrameMeta
from savant.deepstream.pyfunc import NvDsPyFuncPlugin
from savant.gstreamer import Gst
from savant.meta.object import ObjectMeta


def extract_element_name(fullname: str) -> Tuple[str, str]:
    name_parts = fullname.split(".")
    assert len(name_parts) == 2
    return name_parts[0], name_parts[1]

class CreateROI(NvDsPyFuncPlugin):
    """This class will create custom regions of interest where OCR will be applied.

    Args:
        - inputs: list of strings with the full object name (e.g. vehicle.license_plate)
        - roi: name of the fake object that will be generated for OCR (e.g. custom_roi.roi)
    """

    inputs: List[Tuple[str, str]]

    roi_object_element_name: str
    roi_object_label: str

    def __init__(
        self,
        inputs: List[str],
        roi: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.inputs = [extract_element_name(item) for item in inputs]
        self.roi_object_element_name, self.roi_object_label = extract_element_name(roi)


    def process_frame(self, buffer: Gst.Buffer, frame_meta: NvDsFrameMeta):
        objects_for_ocr: List[ObjectMeta] = [
            object_meta
            for object_meta in frame_meta.objects
            if (object_meta.element_name, object_meta.label) in self.inputs
        ]

        # Create a custom ROI object for each object that needs OCR
        for obj in objects_for_ocr:
            child_object_meta = ObjectMeta(
                element_name=self.roi_object_element_name,
                label=self.roi_object_label,
                bbox=obj.bbox,
            )

            frame_meta.add_obj_meta(child_object_meta)

            # The parent must be defined after adding the object to the frame meta
            child_object_meta.parent = obj


class FakeOCR(NvDsPyFuncPlugin):
    """This class create a fake OCR attribute just to make it easier to spot the error.

    Args:
        - attribute: element containing the OCR data (e.g. my_ocr.text)
        - roi: name of the fake object that will be generated for OCR (e.g. custom_roi.roi)
    """

    roi_object_element_name: str
    roi_object_label: str

    attribute_element_name: str
    attribute_name: str

    def __init__(
        self,
        roi: str,
        attribute: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.roi_object_element_name, self.roi_object_label = extract_element_name(roi)
        self.attribute_element_name, self.attribute_name = extract_element_name(
            attribute
        )

    def process_frame(self, buffer: Gst.Buffer, frame_meta: NvDsFrameMeta):
        custom_roi_objects: List[ObjectMeta] = [
            object_meta
            for object_meta in frame_meta.objects
            if (
                object_meta.element_name == self.roi_object_element_name
                and object_meta.label == self.roi_object_label
            )
        ]

        for custom_roi_object in custom_roi_objects:
            custom_roi_object.parent.add_attr_meta(
                element_name=self.attribute_element_name,
                name=self.attribute_name,
                value=1,
                confidence=1,
            )


class MergeROI(NvDsPyFuncPlugin):
    """This class will move the OCR attribute back to the original object.

    Args:
        - attribute: element containing the OCR data (e.g. my_ocr.text)
        - roi: name of the fake object that will be generated for OCR (e.g. custom_roi.roi)
    """

    roi_object_element_name: str
    roi_object_label: str

    attribute_element_name: str
    attribute_name: str

    def __init__(
        self,
        roi: str,
        attribute: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.roi_object_element_name, self.roi_object_label = extract_element_name(roi)
        self.attribute_element_name, self.attribute_name = extract_element_name(
            attribute
        )

    def process_frame(self, buffer: Gst.Buffer, frame_meta: NvDsFrameMeta):
        custom_roi_objects: List[ObjectMeta] = [
            object_meta
            for object_meta in frame_meta.objects
            if (
                object_meta.element_name == self.roi_object_element_name
                and object_meta.label == self.roi_object_label
            )
        ]

        for custom_roi_object in custom_roi_objects:
            roi_attribute = custom_roi_object.get_attr_meta(
                self.attribute_element_name,
                self.attribute_name,
            )

            # If the custom ROI has the attribute we're interested in, copy it to the original object
            if roi_attribute is not None:
                # Copy the attribute to the original object.
                custom_roi_object.parent.add_attr_meta(
                    element_name=roi_attribute.element_name,
                    name=roi_attribute.name,
                    value=roi_attribute.value,
                    confidence=roi_attribute.confidence,
                )

            # Remove the custom ROI
            frame_meta.remove_obj_meta(custom_roi_object)
