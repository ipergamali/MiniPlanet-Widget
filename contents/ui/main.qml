import QtQuick 6.5
import QtQuick.Layouts 6.5
import QtQuick.Controls 6.5 as Controls
import Qt5Compat.GraphicalEffects
import org.kde.plasma.core 6 as PlasmaCore
import org.kde.plasma.components 6 as PlasmaComponents
import org.kde.plasma.plasmoid 2.0

Item {
    id: root
    width: PlasmaCore.Units.gridUnit * 14
    height: PlasmaCore.Units.gridUnit * 14

    property var planetData: ({
        temp: "--",
        condition: "Loading",
        is_day: true,
        moon_phase: "new"
    })

    readonly property url dayTexture: Qt.resolvedUrl("../../assets/planet_day.png")
    readonly property url nightTexture: Qt.resolvedUrl("../../assets/planet_night.png")

    readonly property string scriptPath: {
        const url = Qt.resolvedUrl("../scripts/planet_data.py")
        if (!url)
            return ""
        if (url.startsWith("file://")) {
            if (url.startsWith("file:///")) {
                return url.substring(7)
            }
            return url.substring(7)
        }
        return url
    }

    readonly property string scriptCommand: {
        if (!scriptPath)
            return ""
        const escaped = scriptPath.replace(/(["\\$`])/g, "\\$1")
        return "python3 \"" + escaped + "\""
    }

    function refresh() {
        if (!scriptCommand)
            return
        planetDataSource.connectToSource(scriptCommand)
        refreshTimer.restart()
    }

    PlasmaCore.DataSource {
        id: planetDataSource
        engine: "executable"

        onNewData: function(source, data) {
            disconnectSource(source)
            const stdoutData = data["stdout"] || ""
            if (!stdoutData)
                return
            try {
                const parsed = JSON.parse(stdoutData)
                if (parsed) {
                    root.planetData = {
                        temp: parsed.temp !== undefined ? parsed.temp : root.planetData.temp,
                        condition: parsed.condition || root.planetData.condition,
                        is_day: parsed.is_day !== undefined ? parsed.is_day : root.planetData.is_day,
                        moon_phase: parsed.moon_phase || root.planetData.moon_phase
                    }
                }
            } catch (e) {
                console.warn("MiniPlanet: failed to parse planet_data output", e, stdoutData)
            }
        }
    }

    Timer {
        id: refreshTimer
        interval: 60 * 60 * 1000
        repeat: true
        running: false
        onTriggered: root.refresh()
    }

    Component.onCompleted: {
        refreshTimer.start()
        refresh()
    }

    Rectangle {
        id: cosmicBackdrop
        anchors.fill: parent
        radius: width / 2
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.planetData.is_day ? "#112a6fff" : "#14142b" }
            GradientStop { position: 1.0; color: root.planetData.is_day ? "#0b1c46" : "#060611" }
        }
        opacity: 0.85
    }

    Item {
        id: planetContainer
        anchors.centerIn: parent
        width: Math.min(root.width, root.height) * 0.8
        height: width

        Image {
            id: planet
            anchors.centerIn: parent
            width: parent.width
            height: width
            source: root.planetData.is_day ? root.dayTexture : root.nightTexture
            smooth: true
            fillMode: Image.PreserveAspectFit
            transformOrigin: Item.Center
            antialiasing: true

            NumberAnimation on rotation {
                from: 0
                to: 360
                duration: 10000
                loops: Animation.Infinite
            }
        }

        DropShadow {
            anchors.fill: planet
            source: planet
            horizontalOffset: 0
            verticalOffset: 18
            radius: 36
            samples: 32
            color: root.planetData.is_day ? "#4427a0ff" : "#44224699"
            cached: true
        }

        Image {
            id: moon
            anchors.right: planet.right
            anchors.rightMargin: planet.width * 0.1
            anchors.top: planet.top
            width: planet.width * 0.28
            height: width
            source: Qt.resolvedUrl("../../assets/moon_phases/" + root.planetData.moon_phase + ".png")
            fillMode: Image.PreserveAspectFit
            smooth: true
            opacity: root.planetData.moon_phase ? 0.9 : 0.0
            Behavior on opacity { NumberAnimation { duration: 600 } }
        }

        Rectangle {
            id: aura
            anchors.centerIn: planet
            width: planet.width * 0.9
            height: width
            radius: width / 2
            color: root.planetData.is_day ? "#335eaaf4" : "#331d0b5c"
            opacity: 0.4
            scale: 1.1
            border.width: 0
            visible: true
            Behavior on color { ColorAnimation { duration: 600 } }
        }
    }

    Column {
        id: infoOverlay
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: PlasmaCore.Units.gridUnit * 1.5
        spacing: PlasmaCore.Units.gridUnit * 0.5

        PlasmaComponents.Label {
            text: root.planetData.condition + " · " + root.planetData.temp + "°C"
            font.pixelSize: PlasmaCore.Theme.defaultFont.pixelSize * 1.1
            color: "white"
            opacity: 0.9
            horizontalAlignment: Text.AlignHCenter
            width: parent.width
            wrapMode: Text.NoWrap
        }

        PlasmaComponents.Label {
            text: root.planetData.is_day ? i18n("Daytime sky above") : i18n("Night sky above")
            font.pixelSize: PlasmaCore.Theme.smallestFont.pixelSize
            color: "#d0d6ff"
            opacity: 0.7
            horizontalAlignment: Text.AlignHCenter
            width: parent.width
            wrapMode: Text.NoWrap
        }
    }

    MouseArea {
        id: interactionArea
        anchors.fill: parent
        hoverEnabled: true
        onClicked: root.refresh()
    }

    Controls.ToolTip {
        id: infoTooltip
        visible: interactionArea.containsMouse
        text: i18nc("tooltip text", "%1 · %2°C\nMoon: %3", root.planetData.condition, root.planetData.temp, root.planetData.moon_phase)
        delay: 500
    }
}
